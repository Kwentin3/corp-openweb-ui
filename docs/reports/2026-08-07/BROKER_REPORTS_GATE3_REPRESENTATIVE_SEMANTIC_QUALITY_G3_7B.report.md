# Broker Reports G3.7B Representative Semantic Quality Proof

Status: `COMPLETED_INACTIVE`

Date: 2026-08-07

## GOAL_STATUS

`G3.7B = COMPLETED`; `ACCEPTANCE = PASS`.

## SEMANTIC_QUALITY

`SUFFICIENT_FOR_MVP`.

The final-contract evidence labels common financial facts correctly, preserves
important distinctions through sparse omission, exposes invalid output rather
than repairing it, and leaves unmeasured/unsupported concepts explicit.

## WHAT_WAS_ACHIEVED

- exact instruction diff proved that `1.0.0 → 1.0.1` changed alias
  serialization only, so prior human semantic observations remain admissible;
- seven of nine published labels were observed under the final strict
  contract;
- three positive boundary specimens were correctly labeled;
- eight confusable/ambiguous boundary specimens were correctly omitted;
- no false positive, wrong label or obvious missed fact was found in the
  bounded adjudicated selection;
- two rare labels and one unavailable positive boundary remain explicitly
  `NOT_MEASURED` rather than being replaced by synthetic evidence;
- unsupported concepts remain unsupported instead of being forced into the
  nearest v1 label.

## INSTRUCTION_SEMANTIC_DIFF

Instruction `1.0.0`, SHA-256
`c239af0eb3e4308576b1766d9c84a0a4317d2873c046775a5700a81e5e7ce7b3`,
already owned all financial task semantics:

```text
confident positive facts only
known dictionary labels only
document target aliases only
uncertain -> omission
empty annotations valid
no invented labels/canonical refs
```

Instruction `1.0.1`, SHA-256
`ddce6621e2b64337fb06201bc95f355a06765ce4b66fafdb9e87b4930f47ea8a`,
added exactly one output-format rule:

```text
[t123] -> t123
bare t + digits only
no brackets, Markdown, prefixes or explanations
```

No financial criterion, dictionary meaning, omission rule or classification
task was added, removed or weakened. Repeating the old semantic calls solely
because of this formatting change would add cost without new semantic evidence.

## LABEL_COVERAGE

| Label | Final strict result | Observed annotations |
| --- | --- | ---: |
| `SECURITY_PURCHASE` | `OBSERVED` | 22 |
| `SECURITY_DISPOSAL` | `OBSERVED` | 11 |
| `DIVIDEND_INCOME` | `OBSERVED` | 144 |
| `COUPON_INCOME` | `OBSERVED` | 2 |
| `INTEREST_INCOME` | `OBSERVED` | 12 |
| `SECURITIES_LENDING_INCOME` | `NOT_MEASURED` | — |
| `ACCRUED_COUPON_COMPONENT` | `NOT_MEASURED` | — |
| `TRANSACTION_CHARGE` | `OBSERVED` | 32 |
| `TAX_WITHHELD` | `OBSERVED` | 185 |

Counts combine the complete final-contract compact and large-document proofs.
They describe observed proposals, not corpus prevalence or recall.

## COUNTEREXAMPLE_RESULTS

| Boundary | Result | Evidence basis |
| --- | --- | --- |
| return of capital → not dividend | `CORRECT_OMISSION` | final large-document exact output |
| stock dividend → not cash dividend | `CORRECT_OMISSION` | final large-document exact output |
| dividend accrual | `CORRECT_OMISSION` | final large-document exact output |
| debit interest → not income | `CORRECT_OMISSION` | final large-document exact output plus prior adjudication |
| interest accrual | `CORRECT_OMISSION` | final large-document exact output plus prior adjudication |
| paid coupon | `CORRECT_LABEL: COUPON_INCOME` | final compact exact output |
| transaction НКД | `NOT_MEASURED` | no current reader-visible positive specimen |
| position НКД | `CORRECT_OMISSION` | final compact exact output |
| transaction commission | `CORRECT_LABEL: TRANSACTION_CHARGE` | admissible prior adjudication plus final label observation |
| withholding tax | `CORRECT_LABEL: TAX_WITHHELD` | final large/compact exact outputs |
| tax calculation | `CORRECT_OMISSION` | admissible prior human adjudication |
| REPO purchase context | `CORRECT_OMISSION` | admissible real REPO chunk; no ordinary purchase annotation |

## OMISSION_RESULTS

Sparse omission behaved as designed. Real return-of-capital, stock-dividend,
dividend-accrual, debit-interest, interest-accrual, position-NКД,
tax-calculation and REPO contexts were not forced into positive v1 labels.
Two complete final large-document chunks also returned valid empty arrays.

An omission remains a non-claim. These reviewed cases support boundary quality;
they do not establish universal recall.

## QUALITY_ACCOUNTING

| Outcome | Count |
| --- | ---: |
| `CORRECT_LABEL` | 3 |
| `CORRECT_OMISSION` | 8 |
| `FALSE_POSITIVE` | 0 |
| `WRONG_LABEL` | 0 |
| `MISSED_OBVIOUS_FACT` | 0 |
| `INVALID_OUTPUT` under final contract | 0 |
| `NOT_MEASURED` boundary | 1 |

The earlier compact alias-format rejection remains visible historical evidence
of fail-closed behavior. It is not counted as a current semantic error because
the raw financial choices were aligned and the final strict compact call
validated without repair or retry.

## KNOWN_UNMEASURED_LABELS

- `SECURITIES_LENDING_INCOME`;
- `ACCRUED_COUPON_COMPONENT`.

Real corpus research supports keeping both dictionary entries, but no positive
specimen for either was reader-visible in the active final-contract proof
store. They remain `NOT_MEASURED`, not failed and not synthetically filled.

## KNOWN_UNSUPPORTED_FACTS

- return of capital;
- stock distribution/dividend event;
- REPO event;
- custody/depository charge;
- tax settlement or refund.

These concepts remain source-visible but have no forced v1 financial label.

## WHAT_WAS_REUSED

- G3.3V human-adjudicated real-corpus specimens;
- G3.4C exact model inputs, outputs and manual quality decisions;
- G3.4D final compact strict proof;
- G3.7A complete large-document final proof;
- the published dictionary and existing architecture tests proving that no
  deterministic financial classifier exists.

## WHAT_WAS_ADDED

- one corrected semantic-quality receipt;
- this human-audited quality report.

No runtime, model call, label or semantic rule was added.

## WHAT_WAS_NOT_NEEDED

- repeated live calls for the alias-only instruction change;
- synthetic positive specimens;
- 100% recall or all-label observation;
- deterministic keyword/regex classification;
- dictionary expansion or unsupported-event coercion.

## ACCEPTANCE_EVIDENCE

| Requirement | Result |
| --- | --- |
| known common facts correctly labeled | `PASS` |
| important confusable cases distinguished | `PASS` |
| ambiguous cases may remain unlabeled | `PASS` |
| deterministic financial classifier | `NONE` |
| failures visible, not repaired | `PASS` |
| unsupported concepts remain unsupported | `PASS` |
| universal recall required | `NO` |

## RAW_EVIDENCE

- [safe receipt](./BROKER_REPORTS_GATE3_REPRESENTATIVE_SEMANTIC_QUALITY_G3_7B.receipt.safe.json);
- [G3.7A complete large-document proof](./BROKER_REPORTS_GATE3_FULL_LARGE_DOCUMENT_G3_7A.report.md);
- [G3.4D final compact proof](./BROKER_REPORTS_GATE3_STRICT_ALIAS_G3_4D_LIVE_V2.report.md);
- [G3.4C human adjudication](./BROKER_REPORTS_GATE3_CHUNK_BATCH_LABELING_G3_4C.report.md);
- [G3.3V corpus evidence](./BROKER_REPORTS_GATE3_NDFL_CORPUS_EVIDENCE_G3_3V.report.md).

Exact customer/model values remain in their existing non-Git evidence sets.
G3.7B made zero provider submissions.

## KNOWN_LIMITATIONS

- This is bounded human review, not a statistical production benchmark.
- Two rare label positives and transaction НКД behavior remain unmeasured.
- Visual-only evidence outside the reader-visible contour is not treated as a
  model-quality observation.

## OBSERVATIONS

The final large-document proof materially strengthens the earlier review: it
confirms current-contract empty outputs and several confusable cases while also
showing the common purchase/disposal/dividend/interest/charge/withholding
labels in one complete persisted result.

## KISS_CHECK

`PASS`.

The audit reused exact evidence after proving semantic equivalence of the two
instruction versions. No redundant calls or second classifier were created.

## BLOCKING_OBSERVATIONS

`NONE` for MVP semantic quality.

## ERROR_CLASSIFICATION

No current semantic or contract failure. Unmeasured labels/cases are explicit
coverage limits, not errors.

## AUTO_CONTINUE

`YES`.

## NEXT_GOAL

`G3.7C — Corrected Terminal Gate 3 Proof`.
