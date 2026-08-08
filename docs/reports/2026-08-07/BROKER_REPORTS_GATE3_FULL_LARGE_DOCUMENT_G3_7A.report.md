# Broker Reports G3.7A Full Large-Document Semantic Proof

Status: `COMPLETED_INACTIVE`

Date: 2026-08-07

## GOAL_STATUS

`G3.7A = COMPLETED`; `ACCEPTANCE = PASS`.

One known real large CSV traversed the final Gate 3 contract end to end:
all six existing structural chunks, one LLM submission per chunk, strict
validation, deterministic merge, complete `FinancialAnnotationsV1` sidecar,
persistence and exact read-back.

## WHAT_WAS_ACHIEVED

- all `6/6` structural chunks were submitted and terminally validated;
- provider submissions were exactly six, with zero retry, repair or fallback;
- the exact dictionary was injected once in every request;
- all raw aliases were bare exact members of their own chunk;
- every chunk retained the same document/canonical binding;
- deterministic merge produced 403 validated annotations and
  `document_status=complete`;
- the result was persisted through the G3.5 owner and read back exactly;
- exact canonical and dictionary bindings passed;
- the active Gate 2 canonical version and root hash were unchanged.

## WHAT_WAS_REUSED

- `CanonicalReaderFactory.create` and the existing active canonical document;
- the frozen G3.4B chunker, 60,000-character bound and six known chunks;
- dictionary `broker-reports-financial-labels@1.0.0`;
- instruction `1.0.1` and the strict response schema/validator;
- `Gate3ChunkBatchLabelingFactory.create` for sequential execution/merge;
- the existing structured-model client and provider adapter;
- `Gate3FinancialAnnotationsPersistenceFactory.create` and ArtifactStore.

## WHAT_WAS_ADDED

- one proof-only frozen G3.7A runner;
- one privacy-safe receipt and exact non-Git evidence set;
- one focused proof-contract test.

No maintained Gate 3 runtime contract or behavior was changed.

## WHAT_WAS_NOT_NEEDED

- chunk, budget, dictionary, label, instruction or schema changes;
- alias normalization or output repair;
- semantic retry, fallback model or alternate provider;
- cross-document context;
- a new database, persistence adapter or merge implementation;
- Gate 2 mutation, G3.6 rewrite or Gate 4 execution.

## ACCEPTANCE_EVIDENCE

| Requirement | Result |
| --- | --- |
| all structural chunks submitted | `PASS: 6/6` |
| all chunks terminally validated | `PASS: 6/6` |
| max submissions per chunk | `PASS: 1` |
| semantic retry / repair / fallback | `0 / 0 / 0` |
| dictionary injection | `PASS: 1/request` |
| exact bare aliases | `PASS` |
| cross-document content | `0` |
| deterministic merge | `PASS` |
| document status | `complete` |
| annotations | `403` |
| persistence / exact read-back | `PASS / PASS` |
| canonical / dictionary binding | `PASS / PASS` |
| Gate 2 unchanged | `PASS` |

## TOKEN_EVIDENCE

| Chunk | Input tokens | Output tokens | Duration ms | Annotations |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 41,968 | 311 | 28,687 | 8 |
| 2 | 42,915 | 5,531 | 89,359 | 160 |
| 3 | 40,696 | 4,586 | 57,969 | 226 |
| 4 | 44,511 | 341 | 17,125 | 9 |
| 5 | 43,552 | 23 | 9,844 | 0 |
| 6 | 9,632 | 26 | 10,015 | 0 |
| **Total** | **223,274** | **10,818** | **212,999** | **403** |

Peak input was 44,511 tokens. These measurements describe the current
architecture; G3.7A does not optimize it.

## RAW_EVIDENCE

- [safe receipt](./BROKER_REPORTS_GATE3_FULL_LARGE_DOCUMENT_G3_7A.receipt.safe.json);
- frozen plan SHA-256:
  `65d2fe99119951fbeef3e94e38d9637cf1860e1a99690cead41a6cf4693bc865`;
- complete batch SHA-256:
  `f02b0a85cc06239a49995a2989a178ab106cb80ce5f9eff90501fcc260975664`;
- persisted/read-back payload SHA-256:
  `165e51e0b01be2103606c364b422579c8e97c0071202ee4ca0aaedd26ed14aeb`;
- exact private evidence remains outside Git: 17 files, 8,447,754 bytes;
  manifest SHA-256
  `eca1e6755747be9b4235ede82d15d1ab414bf1abbccd7fdd8d0ead0d7df0f053`;
- focused harness plus batch/persistence regression: `21 passed`;
- targeted Ruff and compile: passed.

The private set contains every exact chunk, context envelope, dictionary,
instruction, final provider request, raw response, validated output, batch,
stored sidecar and read-back value.

## KNOWN_LIMITATIONS

- This is one representative large document, not a corpus-wide throughput or
  semantic benchmark.
- Two chunks validly returned empty sparse annotations; omission remains a
  non-claim.
- Current-case readiness became `2/16`; that downstream fact is not a G3.7A
  semantic acceptance criterion.

## OBSERVATIONS

The exact model was available on the first bounded catalog check. Chunk 3
returned 226 annotations in this run versus 227 in the earlier representative
call; both independently passed the sparse contract. Gate 3 does not promise
identical semantic proposals across separate LLM submissions.

## KISS_CHECK

`PASS`.

The proof used the existing reader, chunker, dictionary, provider route,
validator, merge and persistence owners. The only new executable is a frozen
proof harness for the explicitly missing acceptance path.

## BLOCKING_OBSERVATIONS

`NONE`.

## ERROR_CLASSIFICATION

No implementation, semantic/contract, infrastructure or architectural error
occurred.

## AUTO_CONTINUE

`YES`.

## NEXT_GOAL

`G3.7B — Representative Semantic Quality Proof`.
