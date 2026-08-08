# Broker Reports G3.4C bounded chunk batch labeling live reproof

Status: `PARTIALLY_COMPLETED_INACTIVE`

Date: 2026-08-07

## Outcome

G3.4C proved the intended bounded live route without changing G3.4B or adding a
parallel semantic subsystem. Twelve predeclared chunks were submitted
sequentially through the existing provider adapter and G3.4 validator. Eleven
validated. One compact response was terminally rejected because its four
otherwise known aliases included display brackets rather than the required
bare alias form. No retry, repair or fallback was performed.

The provider-visible schema adapter fix is live-proven: all 12 attempts saw the
schema version as a singleton enum and every raw response returned the exact
schema version. The large CSV completed across all six chunks. Its peak input
fell from 215,810 to 44,459 tokens (-79.399008%), while total input was 222,962
tokens (+3.314026%).

The goal is partial, not complete. The compact document is explicitly
`incomplete`, the REPO document is only a structurally selected 5-of-76 subset,
and manual semantic quality remains `PARTIAL`.

## Frozen execution boundary

- G3.4B implementation hash:
  `203477af5d239c6a358dd3468c6727890fd94d9df8ac718b30fb0aef5edae0ba`;
- exact chunk bound: 60,000 characters;
- exact dictionary: `broker-reports-financial-labels@1.0.0`, nine labels;
- exact G3.4 instruction reused unchanged;
- exact existing provider route reused;
- one submission maximum per selected chunk, sequential execution;
- retry, repair, fallback, persistence and product activation: zero.

The corpus was frozen before execution: compact document all chunks (1), large
CSV all chunks (6), and a predeclared structural REPO subset (5 of 76). The
REPO choice used only structural kind, table identity, row boundaries and size.

## Live accounting

| Document | Coverage | Submitted | Validated | Rejected | Status | Input total | Input peak |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: |
| compact HTML | all 1/1 | 1 | 0 | 1 | `incomplete` | 10,386 | 10,386 |
| large CSV | all 6/6 | 6 | 6 | 0 | `complete` | 222,962 | 44,459 |
| REPO XLSX | structural 5/76 | 5 | 5 | 0 | `representative_subset_validated` | 149,431 | 48,522 |
| total | frozen plan | 12 | 11 | 1 | `partial` | 382,779 | 48,522 |

Across the run, output tokens were 6,423, provider total tokens were 416,396,
and measured duration was 191,092 ms. The large CSV produced 194 validated
annotations. The REPO subset produced valid sparse empty arrays; those are not
negative or completeness claims.

The dictionary plus instruction repeated 24,156 characters across the six
large-CSV requests, 6.834657% of their serialized final model-input
characters. Across all 12 calls the corresponding values were 48,312
characters and 8.245719%. Provider usage does not expose component token
counts, so no dictionary token-share claim is made.

## Rejection and merge behavior

The compact raw response had the exact top-level contract shape, exact schema
version and four dictionary-known label IDs. All four aliases were returned in
display brackets. The validator accepted zero aliases and rejected the whole
proposal with `gate3_labeling_response_contract_invalid`. It was neither
silently normalized nor resubmitted.

Merge behavior is deliberately non-semantic: include validated outputs only,
in selected chunk order and then annotation order; reject an exact duplicate
target/label pair. It does not reconcile labels, infer cross-chunk meaning,
deduplicate concepts or convert an incomplete batch into a complete result.

## Manual semantic review

Ten specimens were adjudicated: four correct labels, five correct omissions,
zero false positives, zero wrong labels, zero obvious missed facts, and one raw
semantic choice inside the contract-invalid compact response. Return of capital
was correctly omitted. Credited-interest positives at the last row of one
chunk and first row of the next were both correct, with zero observed boundary
failure. Debit interest, informational accrual and tax-calculation text were
correctly omitted; a transaction charge and withholding were correctly
labeled.

This sample is not enough for broad semantic acceptance. A positive
accrued-coupon-component specimen and a positive securities-lending specimen
were not tested, and the compact coupon did not reach a validated sidecar.
Therefore `SEMANTIC_QUALITY = PARTIAL` and G3.5 is not recommended before human
review.

## Evidence and privacy

Safe evidence:

- [live receipt](./BROKER_REPORTS_GATE3_CHUNK_BATCH_LABELING_G3_4C.receipt.safe.json);
- [request matrix](../../stage2/research/g3_4c/02_live_request_matrix.safe.csv);
- [peak versus total](../../stage2/research/g3_4c/03_peak_vs_total.safe.md);
- [manual quality](../../stage2/research/g3_4c/04_manual_quality.safe.json);
- [observations](../../stage2/research/g3_4c/07_observations.safe.md);
- [private evidence manifest](../../stage2/research/g3_4c/PRIVATE_EVIDENCE_MANIFEST_G3_4C.safe.json).

Exact final model inputs, raw outputs, validation records, merged results and
manual adjudication are available in non-Git private evidence. Its safe
manifest accounts for 31 files, 151,988,963 bytes, with manifest SHA-256
`6272bd9db56bd87260594d1203413f86d8399c29f86389efc585152c2a034bd5`.
No private location, source value or customer identifier is committed.

The artifact-store tree hash was unchanged before and after the run:
`00c52459979ee2c20d3d3e2f32c766a17f3fb500d1ad4aba817c5e1e059ac0be`.

## Verification

- targeted Ruff for the G3.4C implementation, live script and tests: pass;
- projection/chunking/dictionary/G3.4/G3.4C contract and behavior tests:
  50 passed;
- architecture and KT1 anti-duplication guards: 47 passed, with one unrelated
  existing deprecation warning;
- package compile, live-script CLI load and all three closed-world bundle
  facade projections: pass;
- JSON parse, local links, privacy scan, trailing-whitespace scan, frozen G3.4B
  hash, private-manifest hash and `git diff --check`: pass.

A broad standalone Ruff scan of the legacy package facade is not a clean gate:
it reports 83 `F401` findings outside the G3.4C slice. The selected G3.4C files
and the factory/export architecture guards pass; unrelated facade cleanup was
not taken into this goal.

## KISS and anti-duplication check

`PASS_WITH_EXPLICIT_PARTIAL_RESULT`. One thin batch owner reuses the existing
canonical reader, projection, chunker, dictionary, provider adapter and
validator. There is no second reader, dictionary, response validator, provider
route or semantic classifier. The only merge is deterministic in-memory
concatenation with duplicate-pair rejection. G3.5, ArtifactStore integration,
workflow and product routes were not started.

## Required closeout fields

```text
GOAL_G3_4C = PARTIALLY_COMPLETED_INACTIVE
LIVE_SCHEMA_FIX = PROVEN
LIVE_VALIDATED_CHUNKS = 11_OF_12
DOCUMENTS_TESTED = 3__TWO_FULL_ONE_STRUCTURAL_SUBSET
CHUNKS_SUBMITTED = 12
CHUNKS_VALIDATED = 11
CHUNKS_REJECTED = 1
LARGE_CSV_OLD_PEAK_INPUT_TOKENS = 215810
LARGE_CSV_NEW_PEAK_INPUT_TOKENS = 44459
LARGE_CSV_NEW_TOTAL_INPUT_TOKENS = 222962
CURRENT_60K_CHAR_BOUND = ADEQUATE_FOR_MVP__KEEP_UNCHANGED
SEMANTIC_QUALITY = PARTIAL
BOUNDARY_FAILURES = 0_ON_ADJUDICATED_ADJACENT_BOUNDARY
RAW_MODEL_INPUTS = AVAILABLE_PRIVATE_NON_GIT
RAW_MODEL_OUTPUTS = AVAILABLE_PRIVATE_NON_GIT
PARALLEL_SEMANTIC_CLASSIFIER = NONE
MERGE_SEMANTICS = NONE__DETERMINISTIC_VALIDATED_CONCATENATION_ONLY
KISS_CHECK = PASS_WITH_EXPLICIT_PARTIAL_RESULT
NEXT_ALLOWED_GOAL = G3.5_AFTER_HUMAN_REVIEW
```

G3.5 was not started.
