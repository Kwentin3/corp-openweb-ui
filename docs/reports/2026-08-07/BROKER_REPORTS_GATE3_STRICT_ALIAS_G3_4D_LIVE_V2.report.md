# Broker Reports G3.4D-LIVE v2 final labeling proof

Status: `COMPLETED`

Date: 2026-08-07

## GOAL_STATUS

`G3.4D-LIVE = COMPLETED`; `ACCEPTANCE = PASS`.

The exact approved model became available on bounded availability check 2.
The existing frozen route then made exactly two submissions and validated both
planned results. G3.4 is closed and remains inactive.

## WHAT_WAS_ACHIEVED

- The previously failing compact whole-document case validated with five
  sparse annotations and status `complete`.
- The frozen large-CSV chunk 3 validated with 227 sparse annotations and
  status `representative_subset_validated`.
- All 232 raw aliases were exact members of their current chunk mappings.
- The exact dictionary was injected once in each request.
- ArtifactStore tree bytes were identical before and after live labeling.

## WHAT_WAS_REUSED

- `CanonicalReaderFactory`-backed active canonical reads;
- `Gate3ProjectionFactory`, `Gate3StructuralChunkFactory` and the frozen G3.4B
  structural policy;
- published dictionary `broker-reports-financial-labels@1.0.0`;
- `Gate3ChunkBatchLabelingFactory` and `Gate3BoundedLabelingFactory`;
- the existing `Gate2StructuredModelClientFactory` provider route;
- the strict schema and deterministic validator.

## WHAT_WAS_ADDED

- one privacy-safe live receipt;
- this terminal G3.4D-LIVE report;
- exact execution evidence outside Git.

No maintained implementation, semantic contract, schema, alias grammar,
chunker, dictionary, validator or provider adapter was added or changed.

## WHAT_WAS_NOT_NEEDED

- semantic retry;
- repair prompt or alias normalization;
- fallback model or alternate provider;
- registry, catalog cache, discovery service or monitor;
- persistence or workflow activation inside G3.4D.

## ACCEPTANCE_EVIDENCE

| Requirement | Result |
| --- | --- |
| provider submissions > 0 | `PASS: 2` |
| compact previously failed case | `VALIDATED` |
| bounded chunk regression | `PASS` |
| strict bare alias live | `PROVEN` |
| alias repair layer | `NONE` |
| dictionary injection | `1/request` |
| chunker unchanged | `PASS`, frozen SHA-256 preserved |
| dictionary unchanged | `PASS`, version `1.0.0` |
| validator unchanged | `PASS` |
| complete real document | `PROVEN` |

The provider-visible schema preserved the exact canonical alias description
and did not enumerate aliases. Gemini does not receive the unsupported regex
keyword; the unchanged deterministic validator enforces the canonical bare
alias pattern and exact chunk membership after response parsing.

## RAW_EVIDENCE

- [safe receipt](./BROKER_REPORTS_GATE3_STRICT_ALIAS_G3_4D_LIVE_V2.receipt.safe.json)
- availability checks: `2`;
- exact model/provider: `models/gemini-3.5-flash` / `google_gemini`;
- submissions: `2`;
- chunks validated/rejected/provider-failed: `2 / 0 / 0`;
- compact tokens: input `10438`, output `200`, total `13187`;
- large-chunk tokens: input `40696`, output `7796`, total `60808`;
- response schema SHA-256:
  `59453c7dd4298a7d50f87d6d61be7abb4e5a0573a9b9b366f986407e7263867e`;
- frozen G3.4B module SHA-256:
  `203477af5d239c6a358dd3468c6727890fd94d9df8ac718b30fb0aef5edae0ba`;
- private success evidence: 14 files, 1,887,208 bytes, outside Git.

Exact chunks, final model-visible inputs, raw model outputs and restored
annotations remain in the private evidence set for independent human audit.

## KNOWN_LIMITATIONS

- The large CSV proof covers the predeclared representative chunk, not the
  complete six-chunk document.
- Positive specimens for `ACCRUED_COUPON_COMPONENT` and
  `SECURITIES_LENDING_INCOME` were not present in this frozen live plan and
  remain unmeasured here.
- Sparse omission remains a non-claim, not proof of semantic absence.

## OBSERVATIONS

The first catalog check did not publish the exact model; the second did. This
bounded infrastructure variability did not change model, provider, plan or
contract and did not create a semantic retry.

## KISS_CHECK

`PASS`.

The proof reused one reader, one projection, one structural chunker, one
dictionary, one provider route and one strict validator. No second owner or
future-only infrastructure was introduced.

## BLOCKING_OBSERVATIONS

`NONE`.

## ERROR_CLASSIFICATION

The first catalog miss was `TYPE 3 — TRANSIENT INFRASTRUCTURE FAILURE` before
submission. No semantic or architectural failure occurred. A one-off wrapper
text-matching defect after check 1 was `TYPE 1` and was corrected without
changing product or Gate 3 code; the consumed availability check was not
repeated.

## AUTO_CONTINUE

`YES`.

## NEXT_GOAL

`G3.5 — FinancialAnnotationsV1 Persistence`.
