# OpenWebUI Broker Reports: акт приёмки PDF-нормализации

Дата: 2026-07-12

Контрольный документ: тот же одобренный шестистраничный PDF, который использовался в whole-document Gate 2 proof.

Режим: research/audit. Production PDF pipeline, Gate 2 validators, OpenWebUI core и live bundles не менялись.

## 1. Исполнительный вердикт

Текущий `private_normalized_source_payload_v0` доказуем и воспроизводим, но **не принят как постоянный production artifact**.

```text
STRUCTURAL CORRECTNESS: passed
PROVENANCE CORRECTNESS: passed for the current parser contracts
STORAGE PROPORTIONALITY: failed
LLM PROJECTION READINESS: conditional passed
REPRODUCIBILITY: passed on the controlled PDF
TEMPORARY ARTIFACT CLEANUP: failed / contract absent

OVERALL:
accepted as temporary forensic working state
not accepted as permanent canonical representation
```

Причина: 29 748 B извлечённого текста материализуются в 22 185 586 B JSON. Это 125,7 размера PDF и 745,8 размера видимого текста. Рост создаёт не бизнес-содержание, а одновременное хранение символов, bbox, слов, строк, фрагментов, page-level копий, векторных примитивов, candidate hypotheses и нескольких индексов provenance.

Компактный экспериментальный document/table contract, сохраняющий все 14 table decisions, принятые cells, PDF/page/table coordinates, source refs, checksums и blockers, занимает 155 180 B, или примерно в 143 раза меньше полного normalized payload.

## 2. Пропущенная acceptance boundary

Предыдущая приёмка проверяла:

- полный учёт source refs;
- parser/layout completeness;
- source-value resolution;
- coverage invariants;
- table projection validation;
- приватность и no-RAG guards.

Она не проверяла:

```text
source PDF
→ parser working artifacts
→ permanent normalized artifact
```

Не было отдельного ответа на вопросы:

- какие parser objects должны жить после успешной реконструкции;
- сколько раз хранится одно видимое содержание;
- можно ли воспроизвести accepted table без полного geometry snapshot;
- кто и когда удаляет temporary geometry;
- какой размер permanent representation требует ручного approval.

Это признано пропущенным актом приёмки, а не дефектом source-ref validator.

## 3. Измеренная цепочка

| Представление | Uncompressed | Gzip | Отношение к PDF | Отношение к text layer |
|---|---:|---:|---:|---:|
| Source PDF | 176 458 B | PDF уже сжат | 1,00 | 5,93 |
| Extracted visible text | 29 748 B | отдельно не сохраняется | 0,17 | 1,00 |
| Full normalized source document | 22 185 586 B | 3 596 493 B | 125,72 | 745,79 |
| Normalized source units, 20 | 2 121 984 B | 448 659 B | 12,03 | 71,33 |
| Normalized table projections, 14 | 1 771 052 B | 324 723 B | 10,04 | 59,53 |
| Compact canonical experiment, all 14 decisions | 155 180 B | 37 855 B | 0,88 | 5,22 |

Full normalized payload contains:

- 76 810 objects;
- 45 200 arrays;
- 423 525 strings;
- 27 645 visible-text leaf occurrences;
- 172 842 B visible-text occurrences versus 83 084 B unique strings.

Measured duplicate visible-text ratio inside the normalized document is 51,9%. This is only exact-string duplication; structural duplication through refs, indexes and repeated envelopes is additional.

## 4. Component-by-component storage audit

Percentages use 22 185 586 B as denominator. `Gate 2` means direct or indirect consumption in the current source-unit/table path.

| Component | Count | JSON | Gzip | Share | Producer → consumer | Gate 2 use | Reproducible | Classification / retention |
|---|---:|---:|---:|---:|---|---|---|---|
| Characters/glyphs | 19 512 | 7 032 627 B | 776 802 B | 31,7% | pdfplumber layout → geometry builder | no direct use | yes, from PDF + parser version | temporary parser state; compressed debug TTL on failure |
| Bbox inventory | 29 638 | 5 242 326 B | 732 494 B | 23,6% | geometry builder → words/lines/tables | indirect | yes | full inventory temporary; selected table/cell bbox permanent |
| Page inventory | 6 envelopes, 2 596 nested objects | 2 309 015 B | 670 765 B | 10,4% | text/layout parser → unit builder | indirect | yes | compact page manifest permanent; expanded nested copies cache/debug |
| Vector lines | 8 548 | 2 242 923 B | 284 824 B | 10,1% | layout parser → table candidate detector | no after reconstruction | yes | temporary parser state; delete after accepted reconstruction |
| Words | 3 293 | 1 371 998 B | 228 725 B | 6,2% | layout-unit builder → source values/table evidence | yes for selected evidence | yes | selected words/source refs permanent; full inventory recomputable cache |
| Table candidate inventory | 14 | 1 068 054 B | 275 904 B | 4,8% | detector → table reconstruction | yes | yes | compact decision/bbox/status permanent; full hypothesis debug TTL |
| Source-value index | 3 877 | 1 003 459 B | 183 823 B | 4,5% | unit builder → resolver/validator | yes | yes | selected accepted refs permanent; full index recomputable/cache |
| Text fragments | 2 280 | 875 551 B | 82 758 B | text parser → source-unit builder | indirect | yes | compact unit text permanent; full fragments recomputable cache |
| Lines | 274 | 263 624 B | 91 402 B | layout parser → blocks/tables/units | indirect | yes | selected line/region refs permanent; full lines cache/debug |
| Layout coverage | 1 ledger | 251 508 B | 110 935 B | layout-unit builder → validators | yes | yes | permanent compact coverage result; expanded lists may be compressed |
| Source-value refs array | 3 877 | 131 819 B | 59 989 B | unit builder → validators | yes | yes | avoid parallel array when derivable from canonical index |
| Rectangles | 312 | 75 162 B | 12 720 B | layout parser → table detector | no after reconstruction | yes | temporary parser state |
| Parser diagnostics | 3 objects | 740 B | 470 B | parsers → operator/debug | no | yes | compact permanent status; details debug TTL |
| Rejected table projections | 5 | 205 917 B | 43 452 B | reconstructor → coverage/fallback | blocker code is used | yes | compact blocker permanent; full rejected shape debug TTL |
| Accepted table rows | 96 | 43 196 B | 12 891 B | reconstructor → Gate 2 | yes | yes | permanent canonical evidence |
| Accepted table cells | 572 non-empty objects | 454 769 B | 65 371 B | reconstructor → Gate 2 | yes | yes | permanent canonical evidence, but compact field set only |
| Header models | 14 | 22 840 B | 5 764 B | reconstructor → Gate 2 | yes | yes | permanent, subject to stronger header acceptance |
| All table projections | 14 | 1 771 052 B | 324 723 B | table service → Gate 2 | yes | yes | replace current broad envelope with compact canonical projection |

## 5. Почему 30 KB становятся 22 MB

Основные причины количественно:

1. Every glyph is an object: 19 512 objects consume 7,03 MB, although their visible UTF-8 text is 27,7 KB and only 193 B of unique single-character strings.
2. Geometry is normalized into 29 638 separate bbox objects: 5,24 MB.
3. The same page content is represented at char, word, line, fragment, page and table-projection levels.
4. Vector primitives used to discover ruled tables remain stored after candidate decisions: 2,32 MB for vector lines and rectangles.
5. Word text is repeated: 26 435 B occurrences versus 10 039 B unique word strings.
6. Text fragments repeat 29 743 B into 17 428 B unique strings; table projections repeat 18 964 B into 7 566 B unique values.
7. Index and ref arrays coexist even where one is derivable from the other.
8. Rejected hypotheses retain broad structural envelopes instead of only decision evidence.

This volume is useful while proving parser behavior. It is not necessary to keep every object permanently to retain evidence reproducibility.

## 6. Required permanent evidence

The minimum permanent PDF contract must retain:

- document id and original PDF SHA-256;
- original PDF artifact ref and retention state;
- parser engine/version, config hash and projection policy version;
- page number/ref and page checksum;
- table id, page-local bbox and table decision status;
- header hierarchy and row/column ordering;
- accepted rows/cells including empty-cell positions;
- exact visible cell text or candidate-bound value refs;
- cell/table bbox where the parser can prove it;
- source-value ref, source word/cell ref and value checksum;
- structural confidence, ambiguity and blocker codes;
- compact coverage result and unaccepted table decisions;
- reproducibility and validation result.

It does not require permanent storage of every glyph, every glyph bbox, all vector lines, all page-level parallel text copies or full rejected table hypotheses.

## 7. Conceptual compact contract

```json
{
  "schema_version": "broker_reports_pdf_compact_canonical_document_v1",
  "document": {
    "document_id": "opaque",
    "pdf_artifact_ref": "art_opaque",
    "pdf_sha256": "sha256",
    "page_count": 6
  },
  "parser": {
    "engine": "pdfplumber+pypdf",
    "engine_versions": {},
    "config_hash": "sha256",
    "policy_version": "version"
  },
  "pages": [
    {
      "page_ref": "opaque",
      "page_number": 1,
      "page_checksum_ref": "opaque",
      "tables": [
        {
          "table_id": "opaque",
          "bbox": [0, 0, 0, 0],
          "status": "accepted|blocked|rejected",
          "header_rows": [],
          "rows": [],
          "cells": [
            {
              "row": 1,
              "column": 1,
              "text": "private",
              "text_hash": "sha256",
              "bbox": [0, 0, 0, 0],
              "source_value_refs": [],
              "value_checksum_ref": "opaque"
            }
          ],
          "issues": []
        }
      ]
    }
  ],
  "coverage": {},
  "acceptance_ref": "art_opaque"
}
```

The controlled experiment materialized this concept at 155 180 B for all 14 table decisions. It is a research artifact, not a production schema migration.

## 8. `broker_reports_pdf_normalization_acceptance_v1`

The acceptance record should contain:

```text
schema_version
normalization_run_id
document_id
input_pdf_bytes
input_pdf_sha256
parser_engines_and_versions
parser_config_hash
page_count
text_layer_status
text_visible_bytes
table_candidates_total
tables_accepted_total
tables_blocked_or_rejected_total
rows_total
cells_total
source_refs_registered/accounted/unaccounted
permanent_artifact_refs_and_bytes
temporary_artifact_refs_and_bytes
debug_artifact_refs_and_bytes
compression_ratio
visible_text_to_permanent_ratio
duplicate_visible_text_ratio
structural_validation
provenance_validation
llm_projection_validation
reproducibility_validation
cleanup_status
retention_decision
approval_required
acceptance_status
```

### 8.1 Independent gates

1. Structural correctness: pages/tables/rows/cells and explicit blockers are internally consistent.
2. Provenance correctness: every accepted value resolves to original PDF/page/region/source checksum.
3. Storage proportionality: permanent bytes are explained by permanent contracts, not parser convenience.
4. LLM projection readiness: a bounded semantic projection exists without sending forensic geometry.
5. Reproducibility: original PDF plus parser/config versions reproduce decisions or produce an explicit version drift.
6. Cleanup: temporary and debug artifacts reach terminal deleted/compressed/retained-by-policy states.

No single gate may substitute for another. Complete refs do not imply storage acceptance.

### 8.2 Approval rule

The contract must not require every PDF representation to be smaller than the PDF. Instead:

- any permanent representation materially larger than both visible text and the compact table/document model sets `approval_required=true`;
- approval must list retained components, owner, consumer and retention reason;
- a six-page compact artifact remaining in multi-megabyte range requires component-level justification;
- temporary geometry is excluded from permanent proportionality only when cleanup is proven.

## 9. Lifecycle and retention proposal

```text
original PDF
→ temporary detailed geometry
→ table reconstruction
→ compact canonical document/table model
→ structural/provenance/storage acceptance
→ delete temporary geometry
   or retain gzip debug artifact by explicit TTL
```

| Artifact | Default retention | Exception |
|---|---|---|
| Original approved PDF | permanent under case/source policy | delete with source/case lifecycle |
| Compact canonical document/tables | permanent | superseded versions retained by audit policy |
| Compact acceptance result | permanent | none; it is the decision record |
| Full char/bbox/vector geometry | delete after accepted reconstruction | gzip TTL 24h–7d for blocked/failed proof; longer only explicit incident/legal hold |
| Full word/line inventories | delete/recompute after compact source refs persisted | TTL when needed for parser comparison |
| Rejected hypotheses | keep compact bbox/reason/hash | full shape TTL debug only |
| Raster page/table crops | temporary; delete after model result and validation | TTL for disagreement/human review |
| Provider request/raw output | private TTL under experiment policy | safe hashes/metrics permanent |

Cleanup is a terminal state, not a best-effort background intention.

## 10. Acceptance decision for current artifact

| Gate | Result | Evidence |
|---|---|---|
| Structural correctness | passed | 6/6 usable pages, 14/14 candidate regions accounted, validators fail closed |
| Provenance correctness | passed | exact source refs/checksums retained and resolvable |
| Storage proportionality | failed | 22,19 MB permanent candidate versus 155 KB compact experiment |
| LLM projection readiness | conditional passed | Gate 2 compact context exists, but current stored envelope remains forensic-heavy |
| Reproducibility | passed | local rerun reproduced 22,19 MB shape, 14 candidates and 9 ready/5 blocked decisions |
| Temporary cleanup | failed | no acceptance record owns geometry deletion/compressed TTL |

Required current classification:

```text
private_normalized_source_payload_v0
= temporary parser working state + debug/proof artifact
not permanent canonical evidence
```

## 11. Migration boundary

Keep unchanged:

- original PDF as system evidence;
- parser/version/config provenance;
- source refs, checksums and fail-closed validators;
- table coverage/fallback decisions;
- ArtifactStore private access and process=false intake.

Next implementation slice, only after approval:

1. Add compact canonical PDF/table artifact builder beside current artifacts.
2. Add `broker_reports_pdf_normalization_acceptance_v1` validator.
3. Prove compact-to-PDF source-value resolution for accepted tables.
4. Add lifecycle terminal states for geometry/debug artifacts.
5. Run dual-write comparison on the same PDF; do not delete current artifacts until equivalence is proven.
6. Only then deprecate permanent full geometry.

No Gate 2 agent architecture, Gate 3, CSV/HTML/XLSX, Knowledge/RAG/vector or OpenWebUI core changes belong in this slice.

## 12. Final statuses

Proven:

- `BROKER_REPORTS_PDF_NORMALIZATION_ACCEPTANCE_AUDIT_READY`
- `BROKER_REPORTS_PDF_STORAGE_COMPONENTS_ACCOUNTED`
- `BROKER_REPORTS_PDF_PERMANENT_VS_TEMPORARY_BOUNDARY_READY`
- `BROKER_REPORTS_PDF_COMPACT_CANONICAL_CONTRACT_READY`
- `BROKER_REPORTS_PDF_STORAGE_RETENTION_POLICY_READY`

Acceptance result:

```text
CURRENT 22 MB NORMALIZED ARTIFACT:
NOT ACCEPTED AS PERMANENT PRODUCTION REPRESENTATION

ALLOWED ROLE:
TEMPORARY FORENSIC WORKING STATE / TTL DEBUG PROOF
```
