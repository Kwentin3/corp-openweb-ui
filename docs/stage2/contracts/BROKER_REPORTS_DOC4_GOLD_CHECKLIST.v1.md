# Broker Reports DOC4 Gold Checklist v1

Status: `CONTRACTED_PRIVATE_EXPERIMENT_EVIDENCE`

Schema: `broker_reports_doc4_gold_checklist_v1`

Owner: `PdfViewSemanticAdjudicationFactory.seal_gold`.

An independent adjudicator creates one checklist per frozen PDF before every provider call. The adjudicator sees the original PDF visually and this contract, but not Managed Document, LLM View, either model response, or comparison. Parser output may navigate pages but is never source authority.

Each item has a stable ID, semantic key, category, critical flag, ordinal, explicit status, fact kind, literal/normalized value, exact normalized decimal/date, currency, unit, sign, and one or more bounded PDF pointers. Non-financial items set the financial-only fields to null. The checklist and critical-ID set must both be nonempty. It covers passport, section/table/financial-row order, every critical financial fact, totals, commissions, taxes, balances, and explicit uncertainties. A critical item cannot be downgraded. Sealing and terminal replay verify that every evidence excerpt occurs on the declared PDF page, contains the claimed source literal when one exists, and that every financial decimal/date plus its normalized value is deterministically derived from that literal. The sealed file binds the PDF SHA-256, source page range, isolation assertions, timezone-bearing creation time, critical IDs, and integrity hash and stays outside Git.

The normative machine authority is [BROKER_REPORTS_DOC4_GOLD_CHECKLIST.v1.schema.json](./BROKER_REPORTS_DOC4_GOLD_CHECKLIST.v1.schema.json).
