# OpenWebUI Broker Reports: deterministic vs raster vs hybrid PDF table experiment

Дата: 2026-07-12

Контрольный документ: тот же одобренный шестистраничный PDF.

Model/profile for VLM arms: existing OpenWebUI connection, `models/gemini-3.5-flash`, temperature 0, strict JSON Schema, no failover.

Production runtime не менялся. Raw crops, cell values, model responses и reference cells находятся только в ignored private local evidence. Отчёт содержит агрегаты, opaque table keys, safe error classes и hashes.

## 1. Executive verdict

Ни один универсальный arm не принят как немедленная production replacement.

Рекомендуется **Option 4 — path by table class**:

- simple, structurally accepted tables: deterministic compact reconstruction;
- multi-row headers, wide tables and continuations: hybrid 200-DPI crop + production word/source-value candidates;
- raster-only: challenge/fallback/human-review path, не authoritative source-fact path;
- disagreements, invalid structured output or missing source refs: human review;
- full coordinate geometry: temporary/debug TTL only.

Raster-only был самым точным единым 150-DPI arm на этом наборе: 98,80% exact cells и 99,08% numeric-like cells. Но он сохраняет только document/page/crop provenance и не может сам доказать точный source value.

Hybrid primary at 150 DPI дал 83,75%/77,85% из-за одного wide multi-row-header case. Adaptive policy, повышающая до 200 DPI только structurally failed case, дала 99,04% exact cells, 99,08% numeric-like cells, 9/9 exact structures and headers. Все 1039 selected word candidates в compact hybrid artifact связаны с production `source_value_ref` и `word_ref`.

Hybrid ещё не готов как automatic production primary: один repeat of the wide trade fragment returned HTTP 200 but invalid JSON, а human-reviewed ground truth и настоящий gridless case отсутствуют.

## 2. Experiment contract

All arms used:

- same PDF checksum;
- same selected table regions;
- deterministic crop bboxes and crop SHA-256;
- same reference rows/cells;
- fail-closed local scorer;
- exact normalized-cell comparison;
- numeric-like exact comparison without tolerance;
- structure and header-row checks;
- hallucinated/omitted-cell accounting;
- private raw evidence / safe aggregate split.

HTTP 200 was not treated as success unless strict output parsed to the expected JSON object. One such invalid JSON repeat received full omission penalty.

Safe aggregate terminal status is `completed_with_failures`: all 30 scheduled jobs reached a recorded terminal outcome, but one hybrid repeat failed local parse/schema acceptance. This status is intentionally not `passed`.

## 3. Reference set

### 3.1 Construction

The six rendered pages were visually inspected independently of the production table projection. PyMuPDF table finding/text extraction produced the reference draft; table/page boundaries, row/column shapes, multi-row headers and continuation boundaries were then visually checked against raster pages.

Reference status:

```text
agent_visual_reviewed_pending_human_signoff
```

It must not be called human-reviewed until an actual reviewer signs it. Therefore `BROKER_REPORTS_PDF_TABLE_REFERENCE_SET_READY` is not claimed.

### 3.2 Coverage

The independent engine found 14 table regions. Production candidate detection also found all 14.

Nine representative tables/fragments were selected:

| Safe key | Page | Reference shape | Case |
|---|---:|---:|---|
| `1:1` | 1 | 5×10 | ruled table, merged/multi-row header, totals, empty merged positions |
| `1:2` | 1 | 10×3 | simple ruled table, numeric signs and decimals |
| `1:3` | 1 | 8×18 fragment | wide multi-row header, empty cells, subtotals; production blocked |
| `2:2` | 2 | 12×6 fragment | dense long table, dates, descriptions and numeric columns |
| `3:2` | 3 | 12×16 fragment | wide trade table, multi-line headers; production blocked |
| `4:1` | 4 | 10×16 fragment | headerless page continuation; production blocked |
| `4:2` | 4 | 7×11 | grouped header, many empty cells, totals; production blocked |
| `5:3` | 5 | 5×8 | tax summary, merged/section rows; production blocked |
| `5:4` | 5 | 11×6 | multi-line text cells and mixed identifiers |

The controlled PDF has faint or explicit rules in every detected table. A genuine table without a visible grid is absent. That required case is not proven and must be added from another approved document or synthetic fixture before rollout.

## 4. Scoring policy

For each table:

- structure exact: row and column count must match exactly;
- cell exact: NFKC + whitespace-collapse only, no numeric tolerance;
- numeric exact: every reference numeric-like cell must match its position exactly;
- header exact: visually asserted leading header-row count must match;
- non-empty prediction in an expected empty position is `hallucinated_nonempty_cell`;
- empty prediction for expected non-empty is `omitted_nonempty_cell`;
- failed/invalid provider result is scored as an empty table.

Merged-header representation can create a logically equivalent but cell-position-different result. Such cases remain errors under this strict metric and are reported rather than waived.

## 5. Arm A — deterministic compact reconstruction

Path:

```text
PDF
→ pypdf/pdfplumber detailed geometry
→ production table candidates
→ production table projections
→ compact canonical table artifact
```

### Results

- candidate detection: 14/14, recall 100%; no silent table loss;
- ready table projections: 9/14;
- blocked: 5/14, all explicit `pdf_table_geometry_column_structure_insufficient`;
- selected nine-case overall: 322/831 exact cells = 38,75%;
- selected numeric-like: 64/325 = 19,69%;
- exact structures: 4/9;
- compact artifact for all 14 decisions: 155 180 B, gzip 37 855 B;
- normalization runtime: approximately 19–21 seconds locally.

The low overall accuracy is driven by five explicit blocked tables, not silent wrong output.

Among four selected accepted tables only:

- exact cells: 200/218 = 91,74%;
- numeric-like: 64/66 = 96,97%;
- exact structures: 4/4;
- exact multi-row header counts: 0/4.

The current parser is strong on simple body grids and weak on hierarchical headers and complex wide tables. Its `quality=high` does not currently prove the visually expected header hierarchy.

### Provenance

Strong. Accepted cells carry PDF/table/cell bbox refs, source-value refs and checksums. Compact materialization preserves these without char/vector inventories.

## 6. Arm B — raster-only VLM

Path:

```text
PDF page
→ deterministic table/fragment crop
→ PNG at 150 DPI; selected cases also 200 DPI
→ Gemini strict table JSON
```

No OCR preprocessing or hidden repair/failover was used.

### Primary 150-DPI results

- calls: 9 primary, 15 including sensitivity/repeats;
- passed strict outputs: 15/15;
- exact cells: 98,80%;
- numeric-like exact: 99,08%;
- exact structures: 9/9;
- exact header-row counts: 9/9;
- merged-header case `1:1`: 88% cells and 86,36% numeric-like positions because merged labels/numbering were placed differently;
- multi-line dictionary `5:4`: 95,45% cells, numeric-like 100%;
- remaining primary cases: 98,70–100% cells.

### DPI sensitivity

Four difficult cases were run at 150 and 200 DPI:

- three remained exact at both resolutions;
- `4:1` was 16 columns at 150 DPI and 17 at 200 DPI; source values remained exact, but 200-DPI structure failed because of an extra empty column;
- two cases returned different JSON hashes despite equal accuracy.

### Repeatability

- simple table: identical output hash and 100% accuracy on repeat;
- wide trade fragment: both repeats were 100% accurate but hashes differed in non-value output fields.

### Provenance limitation

Raster-only compact result is 25 510 B, but its strongest source binding is:

```text
PDF checksum
page
table bbox
crop checksum
model id
returned row/column position
```

It does not prove which exact PDF word/source-value ref produced each returned value. Post-hoc string matching is not equivalent to model-time evidence binding. Therefore raster-only cannot be the sole authoritative source-fact extractor even though accuracy was high here.

## 7. Arm C — hybrid raster + compact source evidence

Path:

```text
same table crop
+ ordered visible words
+ table-local normalized coordinates
+ candidate ids
+ production word/source-value refs
→ VLM returns candidate ids only
→ deterministic materialization
```

The model is forbidden to return free financial values. Successful results used zero invalid candidate ids.

### Primary 150-DPI results

- calls: 9 primary, 15 including sensitivity/repeats;
- strict parsed outputs: 14/15;
- exact cells: 83,75%;
- numeric-like exact: 77,85%;
- exact structures: 8/9.

Eight of nine primary cases were 100% exact. The exception was wide hierarchical table `1:3`:

- 150 DPI: 18,52% cells, 11,54% numeric-like, incorrect structure;
- 200 DPI: 98,61% cells, exact structure/header;
- failure mode: visual header/grid interpretation, not invented candidate values.

### Adaptive DPI result

When 200 DPI is used only after a 150-DPI structure failure:

- exact cells: 823/831 = 99,04%;
- numeric-like: 322/325 = 99,08%;
- exact structures: 9/9;
- exact header rows: 9/9;
- four misplaced/extra and four omitted cells, concentrated in merged-header representation;
- invalid candidate ids: 0.

### Repeatability

- simple table: identical candidate-binding hash, 100% both runs;
- wide trade fragment run 1: 100%; run 2: HTTP 200 but `JSONDecodeError`, scored as failed.

This is a material operational risk. Strict structured output must be validated and may be retried only under an explicit same-evidence attempt contract; HTTP success is not acceptance.

### Provenance

The compact hybrid artifact contains:

- 1039 selected candidate-evidence records;
- 1039/1039 production `source_value_ref`;
- 1039/1039 production `word_ref`;
- text hashes, production bbox refs and parser text checksums;
- exact binding rows and candidate ids;
- PDF/page/table/crop identity.

Permanent size is 465 549 B, gzip 112 748 B. This is larger than raster-only and deterministic compact artifacts because it retains selected word evidence, but about 47,7 times smaller than the 22,19 MB forensic payload.

## 8. Storage and model-facing comparison

Model totals include 9 primary, four additional DPI jobs and two repeat jobs per arm: 15 calls per arm.

| Metric | Deterministic | Raster-only | Hybrid |
|---|---:|---:|---:|
| Permanent compact bytes | 155 180 | 25 510 | 465 549 |
| Permanent gzip bytes | 37 855 | 4 781 | 112 748 |
| Temporary normalized geometry | 22 185 586 | not required by raster itself | required during experiment to bind production source refs; deletable after compact evidence |
| Temporary crop PNGs | 0 | shared set 776 888 | shared set 776 888 |
| Image bytes sent across calls | 0 | 873 976 | 873 976 |
| Prompt/text bytes across calls | 0 | 3 645 | 331 052 |
| Schema bytes across calls | 0 | 9 930 | 27 429 |
| Serialized request JSON | 0 | 1 184 325 | 1 556 101 |
| Provider input tokens | 0 | 16 734 | 242 194 |
| Provider output tokens | 0 | 24 514 | 44 065 |
| Primary cell accuracy | 38,75% all selected; 91,74% accepted subset | 98,80% | 83,75%; adaptive 99,04% |
| Primary numeric-like accuracy | 19,69% all; 96,97% accepted subset | 99,08% | 77,85%; adaptive 99,08% |
| Primary exact structure | 4/9 | 9/9 | 8/9; adaptive 9/9 |
| Provenance | strongest | table/crop only | candidate-bound word/source-value refs |
| Repeatability | deterministic | values stable in 2/2 pairs; hash 1/2 | one identical pair; one invalid-JSON repeat |
| Failure transparency | strongest | provider/schema/score explicit | provider/schema/candidate/score explicit |
| Implementation complexity | current geometry logic is high | low extraction logic, weak evidence contract | medium/high orchestration, simpler visual reconstruction, strong binding contract |

Hybrid input tokens are about 14,5 times raster-only in this run because the compact word candidate list is text-heavy. It reduces permanent forensic geometry, not necessarily provider tokens.

## 9. Safe failure examples

### Deterministic

- five real table candidates blocked with `pdf_table_geometry_column_structure_insufficient`;
- wide portfolio, trade start, trade continuation, grouped securities movement and tax summary were among blocked cases;
- accepted hierarchical headers were flattened to one header row.

### Raster-only

- merged-header positions produced three extra and three omitted non-empty cells in `1:1`;
- 200 DPI introduced an extra empty column in continuation `4:1` while 150 DPI was structurally exact;
- output hashes can differ without value accuracy changing.

### Hybrid

- wide `1:3` at 150 DPI mis-grouped rows/columns while 200 DPI was near-exact;
- one repeated wide-table call returned invalid JSON despite HTTP 200;
- candidate binding prevents invented values, but it does not prevent selecting a valid source word into the wrong cell.

No failure was repaired by weakening the scorer, source refs or Gate 2 validators.

## 10. Critical evaluation

### Deterministic risks proven

- brittle column reconstruction on five of fourteen tables;
- incomplete multi-row header model;
- 22 MB parser artifact if intermediates are retained permanently;
- custom geometry maintenance burden.

### Raster risks proven

- merged-header positional ambiguity;
- DPI-dependent extra column;
- non-identical repeat hashes;
- no authoritative cell-level source provenance.

Not proven on this set: digit substitution in body financial values, tiny-font total failure, crop miss or model hallucination outside a supplied crop. These remain required corpus tests.

### Hybrid risks proven

- strong DPI sensitivity on one wide table;
- high candidate-context token volume;
- invalid JSON on one repeat;
- exact provenance does not guarantee correct cell assignment.

Hybrid advantages proven:

- eight of nine 150-DPI primary cases exact;
- adaptive result slightly exceeded raster-only cell accuracy;
- all selected values bind to existing source evidence;
- complex tables blocked by production geometry were recoverable;
- permanent artifact remains sub-megabyte.

## 11. Recommended production roles

### Primary path by table class

1. Deterministic compact path for simple single-header tables only when stronger structural acceptance passes:
   - exact row/column coverage;
   - header hierarchy accepted;
   - source-value resolution complete;
   - no split/merged ambiguity;
   - compact artifact materialized.
2. Hybrid 200-DPI candidate-bound path for:
   - multi-row/merged headers;
   - wide tables;
   - page continuations;
   - deterministic `column_structure_insufficient`;
   - visually irregular but text-layer-readable tables.

### Fallback/challenge

Raster-only VLM is a challenge and candidate-generation path:

- compare structure/value hashes with deterministic/hybrid;
- flag disagreements;
- never directly materialize authoritative financial facts without source-value binding.

### Human review

Required when:

- reference/candidate source refs are incomplete;
- strict JSON fails after bounded same-evidence retry;
- raster and hybrid disagree on numeric-like cells;
- DPI variants disagree structurally;
- merged headers remain ambiguous;
- crop/page/table boundary is uncertain;
- no text-layer candidate can reproduce a returned value.

### Proof/debug

- keep full geometry only for failed/ambiguous cases under compressed TTL;
- keep crops/raw provider outputs private under experiment/incident TTL;
- keep safe metrics, hashes, compact decisions and acceptance records permanently.

## 12. Acceptance thresholds before rollout

Hard thresholds:

- zero silent table loss;
- zero free-form invented financial values in accepted results;
- exact production source-value provenance for every accepted value;
- exact row/column structure or explicit unsupported/ambiguous status;
- zero unexplained source refs;
- strict JSON and post-validation required;
- no permanent 22 MB geometry artifact without explicit component approval;
- temporary geometry reaches proven cleanup/TTL terminal state;
- Gate 2 source-fact validators remain unchanged.

Corpus thresholds to define after actual human reference sign-off:

- exact numeric accuracy target;
- merged-header accuracy target;
- repeatability target;
- allowed provider/schema failure rate and bounded retry policy.

This experiment does not meet rollout acceptance because the reference lacks human sign-off, no true gridless case exists, and hybrid repeatability was not perfect.

## 13. Migration boundary and next slice

Keep production unchanged.

Smallest next implementation slice:

1. Implement research-only `broker_reports_pdf_compact_canonical_document_v1` builder beside current output.
2. Implement normalization acceptance record and temporary-geometry lifecycle.
3. Add stronger deterministic header/merged-cell validation.
4. Build hybrid request from production words/source refs directly, not a parallel tokenizer.
5. Add same-evidence attempt journal and strict terminal parsing.
6. Obtain human sign-off on the nine cases and add a genuine gridless case.
7. Rerun the three arms; only then decide whether the table-class router may enter production.

No Gate 2 agent architecture migration, Gate 3, tax/declaration/XLSX, CSV/HTML/XLSX refactor, Knowledge/RAG/vector or OpenWebUI core patch belongs in this slice.

## 14. Reproducible harness

Research script:

```text
services/broker-reports-gate1-proof/scripts/local_pdf_table_approach_experiment.py
```

Observable scorer tests:

```text
services/broker-reports-gate1-proof/tests/test_broker_reports_pdf_table_experiment.py
```

The harness supports per-call private checkpoints and resume. A failed provider/parse terminal is persisted and penalized; it does not abort or silently disappear.

## 15. Final statuses

Proven:

- `BROKER_REPORTS_PDF_DETERMINISTIC_ARM_COMPLETED`
- `BROKER_REPORTS_PDF_RASTER_ARM_COMPLETED`
- `BROKER_REPORTS_PDF_HYBRID_ARM_COMPLETED`
- `BROKER_REPORTS_PDF_TABLE_APPROACHES_COMPARED`
- `BROKER_REPORTS_PDF_PROVENANCE_STRATEGY_READY`
- `BROKER_REPORTS_PDF_STORAGE_RETENTION_POLICY_READY`
- `BROKER_REPORTS_PDF_TARGET_TABLE_PIPELINE_RECOMMENDATION_READY`

Not proven:

- `BROKER_REPORTS_PDF_TABLE_REFERENCE_SET_READY` — pending actual human sign-off;
- universal gridless-table performance — controlled PDF has no such case;
- production rollout readiness;
- zero-error corpus-level table extraction.

Terminal experiment verdict:

```text
DETERMINISTIC:
primary for simple tables after stronger header acceptance

HYBRID 200 DPI + SOURCE CANDIDATES:
primary candidate for complex tables, not yet rollout-ready

RASTER-ONLY:
high-accuracy challenge/fallback, not authoritative provenance

FULL 22 MB GEOMETRY:
temporary/debug only
```
