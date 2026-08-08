# Broker Reports G3.7 terminal Gate 3 end-to-end proof

Status: `SUPERSEDED_BY_CORRECTED_G3_7C_SCOPE`

Date: 2026-08-07

> Superseded: this report incorrectly treated completion of the current tax
> case as Gate 3 system acceptance. See the
> [corrected G3.7C terminal proof](./BROKER_REPORTS_GATE3_CORRECTED_TERMINAL_G3_7C.report.md).

## GATE3_STATUS

`NOT_READY`.

## END_TO_END

`FAIL`.

The exam did not modify the system or submit a provider request. The current
contour proves its 20 architectural/contract invariants, but the required
representative current-version end-to-end corpus is incomplete. In particular,
the case has only one Gate 3-ready document out of 16, and no large chunked
document has traversed the final strict contract through complete persistence
and case readiness.

## WHAT_GATE3_GUARANTEES

- Gate 2 canonical content is immutable and remains the non-financial source;
- each document has an independent projection, chunk and labeling path;
- large projections use the fixed structural 60,000-character chunker;
- the chunker has no financial/keyword selection;
- `broker-reports-financial-labels@1.0.0` is the sole meaning owner and is
  injected exactly once per request;
- the LLM is the only financial-label selector;
- deterministic code accepts only known labels and exact bare current-chunk
  aliases, with invalid output rejected without repair/retry/fallback;
- sparse omission and valid empty annotation arrays make no absence claim;
- merge is order-preserving and non-semantic;
- complete annotations are immutable sidecars bound to exact canonical,
  dictionary, instruction, model and provider identities;
- case readiness and fixed follow-up permissions are code-owned;
- Gate 4 handoff is fail-closed;
- current-route Financial Domain and Gate 4 tax logic are absent.

## WHAT_GATE3_DOES_NOT_GUARANTEE

- exhaustive recognition of all financial events or labels;
- semantic recall from an omitted annotation;
- tax base, cost basis, FIFO, reconciliation or declaration correctness;
- support for every ambiguous, visual-only or unsupported source fact;
- completion of a document or case merely because Gate 2 is ready;
- readiness of the current 16-document case for Gate 4.

## REAL_CORPUS_RESULTS

| Evidence slice | Result |
| --- | --- |
| compact HTML, final strict contract | complete labeling, five validated annotations, persisted/read back, current case sidecar |
| large CSV, final strict contract | one predeclared chunk validated with 227 annotations; not a complete document and not persisted |
| large CSV, earlier G3.4C contract | all 6/6 chunks validated and merged; predates final instruction `1.0.1` and was not persisted |
| REPO XLSX, earlier G3.4C contract | 5/76 structural chunks validated with empty sparse outputs; representative subset only and not persisted |
| current multi-document case | Gate 2 `16/16`; Gate 3 `1/16`; Gate 4 handoff disabled |
| dictionary corpus | BCS, IBKR, Otkritie, Sber and VTB families reviewed; ambiguity, counterexamples and unsupported facts are documented, but not all were exercised by the final live classifier |

Thus several families and formats exist across the evidence corpus, but only
the compact document has a complete final-contract path through persistence.
That is insufficient for the required representative end-to-end proof.

## LABELING_FAILURES

- No semantic/contract failure occurred in the final two G3.4D submissions.
- The earlier G3.4C compact response was terminally rejected for decorated
  aliases; this correctly proves fail-closed behavior and was not repaired.
- Positive `ACCRUED_COUPON_COMPONENT` and `SECURITIES_LENDING_INCOME` were not
  present in the frozen final live plan.
- Correct omissions and valid empty outputs were adjudicated in G3.4C, but not
  re-established across the final instruction version and persisted contour.
- Ambiguous/unsupported examples are strong dictionary-research evidence, not
  final live classification evidence.

## CONTEXT_AUDIT

`PASS` for the two final representative requests.

Private, non-Git evidence contains the exact chunk, context envelope,
dictionary JSON/Markdown, instruction, response schema, final provider request,
model-visible request, raw provider/model response, validated output and
execution/token metadata for both the compact document and large-CSV chunk 3.
The safe hashes match the inspected files. Token accounting is available:
compact `10438 / 200 / 13187` and large chunk `40696 / 7796 / 60808`
(input/output/total).

One evidence-hygiene defect remains: the private G3.4D success manifest reuses
the G3.4C manifest schema and says `goal=G3.4C`. The individual file hashes and
safe G3.4D receipt remain consistent and readable, but G3.7 records this defect
and does not repair it.

## PERSISTENCE_AUDIT

`PASS` for the one complete compact document; `FAIL` for representative corpus
coverage.

The compact result was saved/read as a separate immutable private
`FinancialAnnotationsV1` sidecar with exact canonical/dictionary/instruction/
model/provider binding. Wrong-user access and overwrite failed closed;
retention/purge owners were reused and Gate 2 was unchanged.

The final-contract large-CSV evidence is only a representative chunk, so it is
correctly not published as a complete sidecar. No other current case document
has a complete G3.5 sidecar.

## MULTI_DOCUMENT_AUDIT

`PASS` for workflow correctness; `NOT READY` for case completion.

The derived case snapshot is deterministic and left ArtifactStore bytes
unchanged. All 16 documents have active Gate 2 canonical versions, exactly one
has a current complete Gate 3 sidecar, and no phantom completion is reported.
`PREPARE_DECLARATION=false` with reason `GATE3_CASE_NOT_READY`.

## KNOWN_UNSUPPORTED_CASES

- visual-only sources without an addressable text/canonical semantic surface;
- return of capital, stock distributions, REPO events, custody/depository
  charges and tax settlement/refund as dedicated v1 labels;
- ambiguous literals without event, direction, amount and table/section scope;
- broad positive acceptance for accrued-coupon transaction components and
  securities-lending income;
- any Gate 4 tax calculation or declaration behavior.

## ACCEPTANCE_MATRIX

| # | Final invariant | Result |
| ---: | --- | --- |
| 1 | Gate 2 immutable | `PASS` |
| 2 | no cross-document labeling | `PASS` |
| 3 | bounded large-document chunks | `PASS` |
| 4 | structural-only chunker | `PASS` |
| 5 | one dictionary owner | `PASS` |
| 6 | dictionary once/request | `PASS` |
| 7 | LLM only semantic classifier | `PASS` |
| 8 | only known labels | `PASS` |
| 9 | exact bare aliases | `PASS` |
| 10 | invalid output fail-closed | `PASS` |
| 11 | sparse omission valid | `PASS` |
| 12 | deterministic-only merge | `PASS` |
| 13 | separate FinancialAnnotations | `PASS` |
| 14 | exact canonical binding | `PASS` |
| 15 | exact dictionary binding | `PASS` |
| 16 | code-owned multi-document state | `PASS` |
| 17 | fail-closed Gate 4 handoff | `PASS` |
| 18 | exact model context auditable | `PASS` |
| 19 | Financial Domain absent | `PASS` |
| 20 | Gate 4 tax logic absent | `PASS` |

These invariants are necessary but do not replace the representative
end-to-end corpus requirement, which failed for the reasons above.

## RAW_EVIDENCE

- [terminal safe receipt](./BROKER_REPORTS_GATE3_TERMINAL_END_TO_END_G3_7.receipt.safe.json);
- [G3.4D final live report](./BROKER_REPORTS_GATE3_STRICT_ALIAS_G3_4D_LIVE_V2.report.md);
- [G3.5 persistence report](./BROKER_REPORTS_GATE3_FINANCIAL_ANNOTATIONS_G3_5.report.md);
- [G3.6 readiness report](./BROKER_REPORTS_GATE3_NDFL_CASE_READINESS_G3_6.report.md);
- [G3.4C batching/omission report](./BROKER_REPORTS_GATE3_CHUNK_BATCH_LABELING_G3_4C.report.md);
- [G3.3V real-corpus dictionary evidence](./BROKER_REPORTS_GATE3_NDFL_CORPUS_EVIDENCE_G3_3V.report.md).

Exact private evidence stays outside Git. G3.7 read it only for audit and made
zero provider submissions, runtime writes or ArtifactStore mutations.

## KISS_CHECK

`PASS`.

G3.7 added only this terminal report and safe receipt. It did not create a new
runtime, schema owner, retry, provider route, persistence layer or workflow.

## GOAL_STATUS

`G3.7 = COMPLETED`; terminal result is `NOT_READY / FAIL`.

## BLOCKING_OBSERVATIONS

1. Current strict-contract complete large-document labeling through G3.5 is
   absent.
2. The real multi-document case is only `1/16` Gate 3 ready.
3. Current-version end-to-end omission, empty-output and ambiguous/unsupported
   representative coverage is incomplete.

Per the G3.7 contract, these observations were recorded and not fixed.

## ERROR_CLASSIFICATION

Terminal acceptance shortfall: `TYPE 2 — PROOF/ACCEPTANCE FAILURE`; no semantic
retry or repair is authorized. The stale private-manifest goal is a recorded
evidence-hygiene implementation defect and was not changed in G3.7.

## AUTO_CONTINUE

`NO`.

## NEXT_CANDIDATE_GOAL

`NONE`.

`STOP`. Gate 4 was not started.
