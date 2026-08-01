# Broker Reports DOC4 Source Adjudication v1

Status: `CONTRACTED_PRIVATE_EXPERIMENT_EVIDENCE`

Schema: `broker_reports_doc4_adjudication_v1`

Owner: `PdfViewSemanticAdjudicationFactory.seal_adjudication`.

RUN D is the only source-grounded verdict. It binds the frozen PDF checklist, both validated responses, and deterministic comparison. The adjudicator reviews every discrepancy, every critical item, every extra/unsupported fact, every invalid pointer, all totals/commissions/taxes/balances, and at least twenty matched noncritical facts per document or all if fewer exist.

Dispositions distinguish arm correctness, both-correct, each wrong arm, both-wrong, artifact semantic gap, native-PDF model gap, general model failure, prompt/schema failure, and source ambiguity. PDF ARM is not presumed correct. Each finding records per-arm correctness, unsupported status, and source-pointer validity. The sealer checks source/response/comparison hash bindings, full gold and discrepancy coverage, every extra and critical model item, special financial kinds, facts citing UNKNOWN View blocks, and the required matched-noncritical sample.

Metrics include critical and noncritical correct/missing/wrong/unsupported counts, exact six-decimal precision/recall, exact numeric/date/currency matches, pointer validity, structure order, artifact/native-model gaps, both-wrong and stability conflicts. Per-document model adequacy is fail-closed against the DOC4 thresholds; final four-document policy remains runner-level.

The normative machine authority is [BROKER_REPORTS_DOC4_ADJUDICATION.v1.schema.json](./BROKER_REPORTS_DOC4_ADJUDICATION.v1.schema.json).
