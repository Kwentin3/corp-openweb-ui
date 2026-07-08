# OpenWebUI Broker Reports Data Contract Family Report

Status: DATA_CONTRACT_FAMILY_DRAFT_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL docs-only contract family

## 1. Constraints Observed

- Code was not changed.
- Runtime was not changed.
- OpenWebUI was not populated.
- Knowledge/Prompts/Skills were not loaded.
- XLS/XLSX was not generated.
- PDF/XLSX source documents were not generated.
- Raw customer documents were not used directly.
- Raw customer documents were not copied into the repository.
- Raw customer filenames and private paths were not printed.
- Implementation blueprint was not written.
- Sidecar UI was not created.
- Secrets, keys and environment values were not read or printed.
- Final tax correctness was not claimed.
- Automatic 3-NDFL completion was not claimed.
- FNS filing was not claimed.

## 2. Documents Studied

- `docs/stage2/contracts/BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0_1_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_SOURCE_FACTS_SCHEMA.v0_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_NDFL_DECLARATION_DATA_MODEL.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_NDFL_DECLARATION_DATA_MODEL.v0_1_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_TAXONOMY.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_EXTRACTION_TO_DECLARATION_MAPPING.v0.md`
- `docs/stage2/domain/BROKER_REPORTS_NDFL_OFFICIAL_REQUIREMENTS_REGISTRY.md`
- `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_METHODOLOGY_INTAKE_PACKET.md`
- `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json`
- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INTAKE_INDEX.report.md`
- selected existing Broker Reports field mapping, review checklist and synthetic ledger design docs under `docs/stage2/`.

## 3. Why One Large Contract Is Worse

The older `broker_reports_extraction_v0` is useful for first proof JSON, but it combines inventory, extracted facts, aggregates, issues and readiness in one response shape.

For a real proof on a selected case group, that shape is too easy to overclaim:

- document metadata can become mixed with source facts;
- source facts can become mixed with calculated ledgers;
- LLM totals can masquerade as deterministic calculation;
- official form structure can be confused with taxpayer source evidence;
- review readiness can drift into tax correctness wording.

The new family keeps each layer owned and independently checkable.

## 4. Contracts Created

- `docs/stage2/contracts/BROKER_REPORTS_DATA_CONTRACT_FAMILY.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_CASE_PACKAGE_CONTRACT.v0_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_INTERMEDIATE_LEDGERS_CONTRACT.v0_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_REVIEW_STATE_CONTRACT.v0_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_CONTRACT_FLOW_MAPPING.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_CONTRACT_VALIDATION_RULES.v0.md`
- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_DATA_CONTRACT_FAMILY.report.md`

## 5. Top-Level Case Package

The case package is `broker_reports_case_package_v0_proposal`.

It owns:

- `case_id`;
- case status;
- `tax_year`, `form_year`, `official_source_set_id`;
- customer methodology status;
- refs to inventory, source facts, ledgers, declaration model and review state;
- safety flags.

It does not own:

- full source facts;
- ledger rows;
- declaration candidate rows;
- issue bodies;
- customer raw filenames or private paths.

## 6. Source Facts To Intermediate Ledgers

Source facts capture visible evidence:

```text
document_id + source evidence + raw_value + normalized_value + confidence
```

Intermediate ledgers consume source facts and create reviewable rows:

- `income_ledger`;
- `securities_operations_ledger`;
- `fees_expenses_ledger`;
- `withholding_ledger`;
- `currency_conversion_ledger`;
- `conflict_ledger`;
- `calculation_trace`.

The ledger layer records which fields are raw, normalized or calculated. Anything calculated requires deterministic proof. Anything methodology-dependent stays `requires_customer_methodology`.

## 7. Ledgers To Declaration-Oriented Model

Ledgers may feed declaration candidates only through refs:

- `ledger_item_id`;
- `source_fact_id`;
- `official_requirement_refs[]`;
- calculation trace refs;
- methodology status.

The declaration model owns target paths and period-aware official refs. It does not own raw document rows or full ledger history.

## 8. Review State

Review state collects:

- `missing_data`;
- `uncertain_data`;
- `conflicts`;
- `methodology_gaps`;
- `official_source_gaps`;
- `calculation_gaps`;
- `questions_to_specialist`;
- specialist-review readiness.

The only positive readiness target is:

```text
ready_for_specialist_review
```

Not:

```text
ready_for_filing
ready_for_final_tax_result
ready_for_auto_declaration
ready_for_xlsx_generation
```

## 9. Safe Customer Source Index Usage

The safe index currently records:

- 63 indexed files;
- container split: PDF, ZIP, HTML/TXT, CSV, XLSX;
- classes including broker reports, operations tables, dividends reports, fees reports, calculation templates, tax-base calculations and unknown/needs-review files;
- 6 safe case groups.

The contract family uses this only through safe refs:

- `case_group_id`;
- `document_id`;
- safe classification and technical profile;
- safe hashes.

ZIP archives and `unknown_or_needs_review` records remain conditional. The intake readiness in the safe index is not final workflow readiness.

## 10. Ready For Proof

Ready now:

- safe document inventory can anchor a selected case group;
- document taxonomy is available;
- source facts schema proposal is available;
- declaration-oriented model v0/v0.1 proposal is available;
- official requirements registry is available for 2025-oriented draft review;
- intermediate ledgers and review state now have explicit proposal contracts;
- validation invariants now define fail-closed proof rules.

## 11. Still Blocked By Customer Methodology

Blocked or placeholder:

- pilot tax years;
- selected broker/case-group scope;
- complete package definition;
- income category/code mapping;
- fee eligibility;
- dividend/coupon split;
- foreign tax treatment;
- currency rate source/date policy;
- summary/detail conflict precedence;
- accepted source granularity;
- readiness criteria.

All such assumptions remain `requires_customer_methodology` or `placeholder`.

## 12. Recommended Next Steps

1. Pick one safe `case_group_id` for the first real proof.
2. Confirm customer approval boundary for using that group's documents as source evidence.
3. Record pilot `tax_year`, `form_year` and `official_source_set_id`.
4. Run source-fact extraction only for approved source-evidence documents.
5. Build intermediate ledgers with calculation gaps explicit.
6. Map only supported candidates to declaration model paths.
7. Produce review state with questions, conflicts and readiness.
8. Validate against `BROKER_REPORTS_CONTRACT_VALIDATION_RULES.v0.md`.

## 13. Final Statuses

```text
DATA_CONTRACT_FAMILY_DRAFT_READY
CASE_PACKAGE_CONTRACT_PROPOSAL_READY
INTERMEDIATE_LEDGERS_CONTRACT_PROPOSAL_READY
REVIEW_STATE_CONTRACT_PROPOSAL_READY
CONTRACT_VALIDATION_RULES_READY
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_NEXT_HUMAN_REVIEW
```
