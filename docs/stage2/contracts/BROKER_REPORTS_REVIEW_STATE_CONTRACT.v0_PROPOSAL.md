# Broker Reports Review State Contract v0 Proposal

Status: Review state contract proposal
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL specialist-review readiness

Global owner: Gate 4 — Tax and Declaration Output Preparation. Earlier gates
own their source issue artifacts; Gate 4 aggregates those refs into the
specialist review state without rewriting source facts or Gate 3 ledgers.

## 1. Purpose

Review state is the contract that collects blockers, warnings, conflicts, methodology gaps and questions.

It is not a declaration, not a tax correctness verdict and not a filing readiness signal. The only positive readiness target is:

```text
ready_for_specialist_review
```

## 2. Top-Level Shape

```json
{
  "schema_version": "broker_reports_review_state_v0_proposal",
  "review_state_id": null,
  "case_id": null,
  "document_inventory_ref": null,
  "source_facts_set_ref": null,
  "intermediate_ledgers_ref": null,
  "declaration_model_ref": null,
  "missing_data": [],
  "uncertain_data": [],
  "conflicts": [],
  "methodology_gaps": [],
  "official_source_gaps": [],
  "calculation_gaps": [],
  "questions_to_specialist": [],
  "readiness": {}
}
```

## 3. Shared Issue Shape

```json
{
  "issue_id": null,
  "issue_type": "missing | uncertain | conflict | methodology_gap | official_source_gap | calculation_gap",
  "severity": "blocking | warning | info",
  "related_document_refs": [],
  "related_source_fact_refs": [],
  "related_ledger_refs": [],
  "related_declaration_model_paths": [],
  "question_to_specialist": null,
  "resolution_status": "open | answered | resolved | deferred"
}
```

Recommended optional fields:

```json
{
  "issue_summary": null,
  "safe_context": null,
  "detected_at_stage": "intake | source_facts | ledgers | declaration_mapping | review",
  "methodology_required": false,
  "official_source_required": false,
  "calculation_required": false,
  "blocks_case_status": []
}
```

`safe_context` must not include raw customer filenames, private paths, account numbers or full financial operation rows.

## 4. Issue Groups

### 4.1. `missing_data`

Use when required evidence or context is absent.

Examples:

- selected case group has no approved source package;
- report/tax year is missing;
- required withholding source is absent;
- source fact lacks source evidence.

Missing data can block extraction, ledger build, declaration mapping or specialist review.

### 4.2. `uncertain_data`

Use when a value exists but is ambiguous, low-confidence or technically weak.

Examples:

- scanned PDF requires OCR/VL OCR;
- mixed income label could be dividend or coupon;
- currency label is absent;
- machine-readable table is partial.

Uncertain data must preserve candidate refs and never be silently upgraded to confirmed.

### 4.3. `conflicts`

Use when two sources or layers disagree.

Examples:

- summary total differs from detailed rows;
- broker report period differs from requested tax year;
- duplicate-looking documents have different metadata;
- withholding amount differs between income and tax sections.

Conflict resolution requires customer methodology or specialist answer.

### 4.4. `methodology_gaps`

Use when customer-owned policy is missing.

Examples:

- fee eligibility;
- foreign tax treatment;
- rate/date policy;
- income code/category mapping;
- source precedence;
- accepted source granularity.

Default status is `requires_customer_methodology`.

### 4.5. `official_source_gaps`

Use when official period or requirement authority is missing or mismatched.

Examples:

- tax year is not 2025 but only the 2025 official source set is present;
- official source set is `pilot_year_pending`;
- target model path has no official requirement ref.

### 4.6. `calculation_gaps`

Use when deterministic calculation is required but not performed or not validated.

Examples:

- lot matching not calculated;
- currency conversion lacks rate/date policy;
- tax-base candidate came from LLM-only arithmetic;
- calculation trace is missing.

## 5. Questions To Specialist

Each question should be concise, safe and actionable:

```json
{
  "question_id": null,
  "priority": "high | medium | low",
  "question_type": "data | methodology | official_source | calculation | readiness",
  "question": null,
  "related_issue_refs": [],
  "blocking_readiness": true,
  "answer_status": "open | answered | deferred"
}
```

Questions must not ask the specialist to validate invented facts. They should point to refs, not raw customer paths.

## 6. Readiness

Suggested shape:

```json
{
  "status": "not_ready | needs_more_data | needs_methodology | needs_calculation | ready_for_specialist_review | blocked",
  "ready_for_specialist_review": false,
  "manual_review_required": true,
  "tax_correctness_claimed": false,
  "fns_filing_claimed": false,
  "xlsx_generation_claimed": false,
  "blocking_issue_refs": [],
  "warning_issue_refs": [],
  "open_question_refs": [],
  "notes": []
}
```

Forbidden readiness meanings:

```text
ready_for_filing
ready_for_final_tax_result
ready_for_auto_declaration
ready_for_xlsx_generation
```

## 7. Readiness Rules

- `ready_for_specialist_review` requires all blocking issues to be answered, resolved or explicitly deferred by approved methodology.
- Warnings may remain open only if methodology says they do not block specialist review.
- `manual_review_required` is always true.
- `tax_correctness_claimed`, `fns_filing_claimed` and `xlsx_generation_claimed` are always false.
- If customer methodology is missing for fee, currency, withholding or income-code treatment, readiness cannot imply final tax correctness.

## 8. Status

```text
REVIEW_STATE_CONTRACT_PROPOSAL_READY
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_NEXT_HUMAN_REVIEW
```
