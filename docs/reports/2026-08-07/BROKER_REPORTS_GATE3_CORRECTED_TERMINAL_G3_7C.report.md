# Broker Reports G3.7C Corrected Terminal Gate 3 Proof

Status: `COMPLETED_READY_FOR_DOWNSTREAM_MVP`

Date: 2026-08-07

This report supersedes the terminal conclusion of
[the earlier G3.7 report](./BROKER_REPORTS_GATE3_TERMINAL_END_TO_END_G3_7.report.md).
That report incorrectly used completion of all documents in one tax case as a
Gate 3 system acceptance criterion.

## GOAL_G3_7C

`COMPLETED`.

## GATE3_SYSTEM_STATUS

`READY_FOR_DOWNSTREAM_MVP`.

Gate 3 is ready as a semantic-labeling mechanism: one complete small real
document and one complete large six-chunk real document passed the final
strict contract through immutable `FinancialAnnotationsV1` persistence, while
representative human semantic quality is sufficient for MVP.

This is not product activation and does not start Gate 4.

## CURRENT_CASE_STATUS

`INCOMPLETE_2_OF_16_DOCUMENTS_PROCESSED`.

The derived G3.6 state currently contains 16 document identities and two
current complete Gate 3 sidecars. Fourteen documents remain unprocessed;
`PREPARE_DECLARATION=false` and downstream handoff remains fail-closed.

This is honest current-case state, not evidence that the Gate 3 mechanism is
unready. A separate read-only survey also found eight remaining active
canonical pointers in this local restore that currently fail reconstruction
with `canonical_chunk_hash_mismatch`; this is case/input debt and was neither
used as Gate 3 semantic acceptance nor repaired here.

## SMALL_DOCUMENT_E2E

`PASS`.

The compact real document passed final instruction `1.0.1`, strict bare aliases,
complete merge, immutable sidecar persistence and exact read-back with five
annotations.

## LARGE_CHUNKED_DOCUMENT_E2E

`PASS`.

The large real CSV passed all six existing structural chunks under the final
contract:

```text
6 submissions
6 validated
0 rejected
0 provider-failed
0 retry / repair / fallback
403 annotations
document_status = complete
persistence = PASS
read-back exact = true
Gate 2 unchanged = true
```

Peak input was 44,511 tokens; total input was 223,274 tokens.

## SEMANTIC_QUALITY

`SUFFICIENT_FOR_MVP`.

Seven of nine labels were observed under the final strict contract. The
bounded adjudicated boundary set had three correct positive labels, eight
correct omissions, zero false positives, zero wrong labels and zero obvious
misses. Ambiguous/unsupported facts stayed unlabeled rather than being forced
into a known label.

## FINANCIAL_DICTIONARY_OWNER

`ONE`: `broker-reports-financial-labels@1.0.0`.

Definitions are not copied into a second prompt, skill, tool, RAG source or
code classifier. The full dictionary is injected exactly once per request.

## PARALLEL_SEMANTIC_CLASSIFIER

`NONE`.

The LLM remains the only selector of financial labels. Deterministic code owns
schema validation, alias membership/restoration, merge order, persistence and
case-state derivation only.

## STRICT_OUTPUT_CONTRACT

`PASS`.

- only published labels;
- only exact bare aliases from the current chunk;
- invalid response fails closed;
- no semantic retry, repair, alias normalization or fallback;
- sparse empty output remains valid.

## PERSISTENCE

`PASS`.

`FinancialAnnotationsV1` is a separate immutable private sidecar. Both the
small and large complete results have exact canonical/dictionary/instruction/
model/provider binding and exact read-back. Existing ArtifactStore access,
retention and purge owners are reused.

## GATE2_MUTATION

`NONE`.

The active canonical version/root remained unchanged in both end-to-end
proofs. Gate 3 reads `CanonicalArtifactV1`; it does not rewrite Gate 2.

## KNOWN_UNSUPPORTED_CASES

- return of capital as its own label;
- stock distribution/dividend event;
- REPO event;
- custody/depository charge;
- tax settlement or refund.

These remain source-visible and deliberately unsupported rather than being
misclassified into the nearest v1 label.

## KNOWN_UNMEASURED_LABELS

- `SECURITIES_LENDING_INCOME`;
- `ACCRUED_COUPON_COMPONENT`.

Their absence from final positive observations does not fail Gate 3. No
synthetic evidence was substituted.

## WHAT_GATE3_GUARANTEES

- `CanonicalArtifactV1` is the only normalized input;
- deterministic LLM-readable projection and sufficient structural context;
- bounded structural chunks for large documents;
- one managed dictionary and sparse positive-only labeling;
- LLM-only semantic selection;
- known labels and strict bare aliases only;
- visible fail-closed invalid output;
- deterministic non-semantic merge;
- separate immutable annotations with exact version bindings;
- exact model context remains auditable outside Git.

## WHAT_GATE3_DOES_NOT_GUARANTEE

- that every current-case document has been processed;
- that a user may begin Gate 4 or prepare a declaration;
- tax base, cost basis, FIFO, reconciliation or declaration generation;
- 100% recall or observation of every label;
- resolution of every unsupported or ambiguous event;
- product-route activation.

## CORRECTED_ACCEPTANCE_EVIDENCE

| Terminal requirement | Result |
| --- | --- |
| canonical-only normalized input | `PASS` |
| readable projection and structural context | `PASS` |
| bounded large-document path | `PASS` |
| one dictionary / LLM-only semantics | `PASS / PASS` |
| sparse strict output / fail-closed invalid | `PASS / PASS` |
| deterministic merge | `PASS` |
| separate immutable persistence and exact bindings | `PASS` |
| complete small real document | `PASS` |
| complete large chunked real document | `PASS` |
| representative semantic quality | `SUFFICIENT_FOR_MVP` |
| exact model context auditable | `PASS` |
| all 16 documents processed | `NOT_AN_ACCEPTANCE_CRITERION` |
| current case Gate 4 ready | `NOT_AN_ACCEPTANCE_CRITERION` |

## RAW_EVIDENCE

- [corrected terminal receipt](./BROKER_REPORTS_GATE3_CORRECTED_TERMINAL_G3_7C.receipt.safe.json);
- [G3.7A full large-document proof](./BROKER_REPORTS_GATE3_FULL_LARGE_DOCUMENT_G3_7A.report.md);
- [G3.7B semantic-quality proof](./BROKER_REPORTS_GATE3_REPRESENTATIVE_SEMANTIC_QUALITY_G3_7B.report.md);
- [G3.5 small-document persistence](./BROKER_REPORTS_GATE3_FINANCIAL_ANNOTATIONS_G3_5.report.md);
- [G3.6 derived case state](./BROKER_REPORTS_GATE3_NDFL_CASE_READINESS_G3_6.report.md).

Exact model/customer evidence remains outside Git. G3.7C made no provider
submission and no runtime or ArtifactStore mutation.

## KISS_CHECK

`PASS`.

The correction removes a downstream tax-case criterion from the upstream
semantic-labeling gate. No new runtime owner, state store or abstraction was
introduced.

## BLOCKING_OBSERVATIONS

`NONE` for Gate 3 system readiness.

The incomplete current case and its local reader reconstruction debt remain
separate downstream/input-state limitations.

## ERROR_CLASSIFICATION

The earlier `NOT_READY` conclusion was a scope/acceptance error: current-case
completion was incorrectly treated as Gate 3 semantic-system completion. The
corrected contract supplied by the user is now the terminal authority.

## NEXT_CANDIDATE

`GATE4_SEPARATE_PROGRAM`.

Gate 4 was not started. `STOP`.
