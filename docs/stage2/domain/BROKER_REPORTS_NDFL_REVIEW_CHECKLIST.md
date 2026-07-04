# Broker Reports NDFL Review Checklist

Status: Draft checklist
Date: 2026-07-04
Scope: human review of `broker_reports_extraction_v0` JSON extraction results

## 1. Scope Check

- [ ] Result is JSON extraction output, not final tax advice.
- [ ] Result does not claim final 3-NDFL generation.
- [ ] Result does not claim FNS filing/submission.
- [ ] `manual_review_warning` is present.
- [ ] `readiness.manual_review_required = true`.
- [ ] `readiness.tax_correctness_claimed = false`.
- [ ] `readiness.fns_filing_claimed = false`.

## 2. Input Completeness

- [ ] Every uploaded/pasted input appears in `document_manifest`.
- [ ] Unsupported/unreadable inputs are still listed.
- [ ] Filenames/source labels are reviewable.
- [ ] Report period is present or missing is explicitly recorded.
- [ ] Duplicate or overlapping documents are identified.

## 3. Document Classification

- [ ] Broker reports are classified as `broker_report`.
- [ ] Operations tables are classified as `operations_table`.
- [ ] Dividend/coupon reports are classified separately where visible.
- [ ] Tax forms are not treated as broker reports.
- [ ] Help articles/instructions are not treated as evidence documents.
- [ ] Unrelated documents are marked `unsupported`, `unknown` or `unrelated` behavior in notes.

## 4. Readability And Processing Mode

- [ ] Text-layer documents are not marked as raster.
- [ ] Machine-readable tables are identified when present.
- [ ] Raster/photo/scanned inputs are marked as `raster_scan`, `photo` or `mixed_text_and_raster`.
- [ ] Raster/vision values are experimental or unsupported.
- [ ] No exact text-layer excerpt is claimed for raster-only content.
- [ ] Limitations are explicit for XLSX formulas, hidden sheets, scans and tables.

## 5. Extracted Facts

- [ ] Taxpayer/client name is present or missing/uncertain.
- [ ] Tax identifier is present or missing/uncertain.
- [ ] Broker account reference is present or missing/uncertain.
- [ ] Broker name is present.
- [ ] Report period is present.
- [ ] Report currency is present or multi-currency limitation is recorded.
- [ ] Sales operations are present or explicitly absent.
- [ ] Purchase/cost basis source is present or missing.
- [ ] Dividends/coupons are present or explicitly absent.
- [ ] Fees/charges are present or missing.
- [ ] Withheld tax is present or missing.
- [ ] Foreign tax is present or missing.

## 6. Evidence Wrappers

- [ ] Every extracted tax-relevant value has an evidence wrapper.
- [ ] `source.document_id` points to an item in `document_manifest`.
- [ ] Page/sheet/row/column is filled when available.
- [ ] `source_type` matches actual source representation.
- [ ] `exact_text_layer_available` is false or null for raster-only values.
- [ ] No extracted fact is based only on unsupported inference.

## 7. Missing Data

- [ ] Missing required fields are in `missing_data`.
- [ ] Blocking missing fields have `blocking = true`.
- [ ] Each blocking missing field has a specialist question.
- [ ] Missing fields are not silently defaulted.

## 8. Uncertain Data

- [ ] Ambiguous values are in `uncertain_data`.
- [ ] Raster-derived values are low-trust unless separately proven.
- [ ] Formula/table parser gaps are uncertain, not accepted as high-confidence.
- [ ] Multi-currency or category ambiguity is explicit.

## 9. Conflicts

- [ ] Conflicting report periods are recorded.
- [ ] Conflicting totals between summary and table are recorded.
- [ ] Conflicting broker/account identifiers are recorded.
- [ ] Conflicts have source references and `resolution_status`.
- [ ] The model did not silently choose a winner without methodology.

## 10. Questions To Specialist

- [ ] Questions are concise and actionable.
- [ ] Questions point to related fields.
- [ ] High-priority blocking questions are marked.
- [ ] Questions do not ask the specialist to validate invented facts.

## 11. Readiness Decision

- [ ] `readiness.status` matches the evidence.
- [ ] Blocking reasons are present when status is not ready.
- [ ] `can_proceed_to_xls_stage` is false unless a later proof explicitly allows it.
- [ ] Result can proceed only to specialist review, not filing.

## 12. Customer Methodology Gate

- [ ] Customer methodology was available, or missing methodology is called out.
- [ ] Required-field list is customer-approved, or marked placeholder.
- [ ] Source precedence rules are approved, or conflicts remain unresolved.
- [ ] Provider/data policy was approved before any real customer data.

## 13. Reviewer Verdict

Allowed verdicts:

- `ACCEPT_FOR_SYNTHETIC_PROOF`
- `NEEDS_REPAIR`
- `NEEDS_MORE_DATA`
- `RUNTIME_EXTRACTION_GAP`
- `REJECT_UNSAFE_OR_OVERCLAIMED`

Reviewer note should explain the blocking reason without adding secrets or real customer data.
