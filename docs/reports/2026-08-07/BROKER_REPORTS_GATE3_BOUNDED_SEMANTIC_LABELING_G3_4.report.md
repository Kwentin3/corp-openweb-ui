# Broker Reports Gate 3 — G3.4 Bounded Semantic Labeling

Status: `PARTIALLY_COMPLETED`

Date: 2026-08-07

## 1. Outcome

G3.4 implements one inactive, non-persisted route:

```text
active CanonicalArtifactV1
-> exact Gate3ProjectionV1
-> exact Managed Financial Label Dictionary v1
-> one minimal instruction
-> existing provider framework
-> raw Gate3LabelingResponseV1 proposal
-> deterministic fail-closed validation
-> in-memory FinancialAnnotationsV1 proposal or terminal rejection
```

The local seam and authority boundaries pass. Four real provider submissions
were made, exactly once per selected canonical document. All four raw responses
were terminal JSON objects, but all used an invalid informal `schema_version`.
The validator rejected every response; no annotation became validated or
persisted.

The common cause was found after the calls: the Gemini schema adapter removed
the response schema's `const` constraint for `schema_version`, leaving an empty
provider-visible property schema. The adapter now projects this constraint as
an equivalent singleton `enum` and is versioned `1.6.0`. Local regression and
frozen provider-proof tests pass. The live calls were not repeated because the
goal forbids retry/repair/fallback.

## 2. Reused authorities

- `CanonicalReaderFactory.create` remains the only canonical read boundary.
- `Gate3ProjectionFactory.create` remains the only G3.2 renderer and alias
  issuer.
- `Gate3FinancialLabelDictionaryFactory.create` remains the only dictionary
  meaning/rendering owner.
- `Gate2StructuredModelClientFactory.create`, its request builder and provider
  adapter remain the only provider route.
- `Gate3BoundedLabelingFactory.create` only composes those owners, executes one
  proposal and validates/restores aliases in memory.

No deterministic financial classifier, keyword-based decision path, old Gate 2
label route, Financial Domain, RAG, Knowledge, Tool, Skill or second prompt
owner was introduced.

## 3. Exact model-input audit

Every real call contained exactly three meaningful model-visible parts:

1. one minimal sparse-positive instruction;
2. the complete exact dictionary rendering, injected once;
3. the exact G3.2 Markdown projection.

There was no hidden history and no model-visible backend alias mapping,
canonical ref, source ref or Broker metadata. The response schema was supplied
separately as strict structured-output configuration. The safe receipt records
`dictionary_injection_count = 1` and `meaningful_context_parts = 3` for all
four calls.

## 4. Representative real corpus

The executed set contained four active reader-visible canonical documents:

- one IBKR-family CSV projection, 318,684 characters and 14,118 aliases;
- three compact HTML projections, 8,506–15,042 characters and 394–640 aliases;
- two source families and both table-heavy and compact document shapes.

The selected set exercises previously adjudicated positive and counterexample
contexts including cash dividend, return of capital, stock distribution,
dividend accrual, credit/debit interest, coupon credit, redemption, trade
charges, withholding and informational position НКД.

REPO XLSX projections were not sent: their exact G3.2 views are 3.6–3.9 million
characters with more than 182,000 aliases, beyond the proof's bounded
500,000-character admission. BCS PDF candidates needed for custody and
securities-lending coverage were not reader-visible in this local store because
the canonical reader rejected their historical chunks. No slicing, source
reread or fallback was used to hide those limits.

Therefore `REPRESENTATIVE_CORPUS = PARTIAL`: the real corpus is useful and
multi-family, but does not live-test REPO, custody or positive securities
lending.

## 5. Provider and validation results

| Measure | Result |
| --- | ---: |
| Planned documents | 4 |
| Provider submissions | 4 |
| Single-submission attempts | 4/4 |
| Provider transport failures | 0 |
| Raw JSON objects with exact top-level fields | 4/4 |
| Unknown aliases | 0 |
| Unknown labels | 0 |
| Duplicate alias/label pairs | 0 |
| Wrong schema versions | 4/4 |
| Validated proposals | 0/4 |
| Persisted annotations | 0 |
| ArtifactStore snapshots unchanged | 4/4 |

The raw proposals contained 377 sparse annotation pairs across the four
documents. These counts are diagnostic only: all 377 remain rejected evidence,
not `FinancialAnnotationsV1` facts.

## 6. Manual quality spot-check

The previously accepted G3.3V evidence was reused as the human reference for a
small, explicit spot-check. Nine pre-adjudicated specimens were reviewed:

- 8 aligned with the dictionary boundary;
- 1 contradicted it: a return-of-capital row was proposed as
  `DIVIDEND_INCOME`;
- stock distribution, dividend accrual, debit interest, interest accrual and
  informational position НКД were not mislabeled in the checked specimens;
- omissions were not counted as negative claims or false assertions.

For the wording specifically requested for observation, the raw proposal had
12 `INTEREST_INCOME` annotations in credit-interest contexts and none on the
reviewed debit-interest or interest-accrual counterexamples. It produced zero
`SECURITIES_LENDING_INCOME` annotations, but the selected reader-visible corpus
had no adjudicated positive BCS lending family, so no quality conclusion is
allowed. The dictionary was not edited.

This spot-check preserves useful model evidence, but it does not override the
closed validator. `LABELING_QUALITY = NOT_ACCEPTED`; the raw semantic diagnostic
is `8/9 aligned`, not a precision/recall estimate and not a Gate 3 pass.

## 7. Evidence and privacy

Exact canonical envelopes, projections, dictionary bytes/rendering,
instruction, model-visible request, final provider request, raw provider
response, raw model output, validated/rejected result, usage, metrics and store
snapshots are available in four per-attempt private evidence files outside Git.
The repository stores only their hashes and privacy-safe aggregates in
[the G3.4 safe receipt](BROKER_REPORTS_GATE3_BOUNDED_LABELING_G3_4.receipt.safe.json).

No customer values, raw contexts or provider outputs are reproduced here.

## 8. Engineering noise removed

Two bounded technical defects were isolated without adding semantic machinery:

1. G3.2 repeatedly scanned every table cell for every row/alias. The same
   deterministic output is now validated in linear passes; focused projection
   tests preserve byte-level behavior.
2. Gemini schema projection removed the `schema_version` constant. It now
   preserves the same constraint as a singleton enum. This correction is
   locally and offline verified but deliberately not live-retried in G3.4.

Generated Function bundles were rebuilt only for closed-world source parity.
Nothing was deployed and no stage/product route was changed.

## 9. Known failures and limitations

- All four real proposals are terminal rejections; there is no validated live
  `FinancialAnnotationsV1` proposal in this run.
- The post-run adapter correction has no fresh live confirmation.
- One reviewed raw proposal confused return of capital with dividend income.
- REPO, custody charge and positive securities-lending coverage remain outside
  the bounded reader-visible live set.
- Sparse omission remains a non-claim; this run does not measure recall.
- G3.5, persistence, workflow, batching and product activation were not started.

## 10. KISS and final status

- one projection owner;
- one exact dictionary owner and one injection;
- one minimal instruction;
- one existing provider framework;
- one closed validator and backend alias restoration;
- zero semantic repair, retry, fallback, persistence or second classifier.

```text
GOAL_G3_4 = PARTIALLY_COMPLETED
REAL_PROVIDER_CALL = YES_4_SINGLE_ATTEMPTS
MODEL_INPUT_AUDIT = PASSED_4_OF_4
DICTIONARY_INJECTION_COUNT = 1_PER_CALL
PARALLEL_SEMANTIC_CLASSIFIER = NONE
REPRESENTATIVE_CORPUS = PARTIAL_4_REAL_DOCUMENTS_2_FAMILIES
LABELING_QUALITY = NOT_ACCEPTED_RAW_SPOT_CHECK_8_OF_9_ALIGNED
RAW_MODEL_INPUTS = AVAILABLE_PRIVATE_HASHED_OUTSIDE_GIT
RAW_MODEL_OUTPUTS = AVAILABLE_PRIVATE_HASHED_OUTSIDE_GIT
ENGINEERING_NOISE = FOUND_AND_REMOVED_LOCALLY_NO_LIVE_RETRY
KNOWN_FAILURES = 4_SCHEMA_VERSION_REJECTIONS; 1_RETURN_OF_CAPITAL_FALSE_POSITIVE; REPO_CUSTODY_LENDING_NOT_LIVE_MEASURED
OBSERVATIONS = INTEREST_WORDING_USEFUL; SECURITIES_LENDING_NOT_MEASURED; DICTIONARY_UNCHANGED
KISS_CHECK = PASSED_WITH_EXPLICIT_LIMITATIONS
NEXT_ALLOWED_GOAL = G3.5_AFTER_HUMAN_REVIEW
```

`G3.5_AFTER_HUMAN_REVIEW` is named only as the next allowed goal. It is not
authorized or started here; the partial live result and no-retry boundary must
be reviewed first.
