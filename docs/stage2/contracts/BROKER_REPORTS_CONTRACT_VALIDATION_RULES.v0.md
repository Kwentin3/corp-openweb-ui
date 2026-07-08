# Broker Reports Contract Validation Rules v0

Status: Validation rules draft
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL contract family invariants

## 1. Purpose

These rules define fail-closed invariants for the Broker Reports contract family.

They are validation rules for proof design and human review. They are not production code and do not claim final tax correctness.

## 2. Identity And Reference Integrity

1. Every case package must have a stable `case_id`.
2. Every public customer-document reference must use safe `document_id` or `case_group_id`.
3. Every source fact must reference at least one safe document inventory item.
4. Every ledger item must reference at least one source fact unless it is an explicit review-only placeholder.
5. Every declaration candidate must reference a ledger item or source fact.
6. Every review issue must reference the related document, source fact, ledger item or declaration model path when available.
7. Child artifacts must not be embedded wholesale into the case package.

## 3. Document Taxonomy And Evidence Rules

8. Classify documents before extraction.
9. Do not use `official_form` as taxpayer source evidence.
10. Do not use `official_filling_instruction` as taxpayer source evidence.
11. Do not use `official_electronic_format` as taxpayer source evidence.
12. Do not use `broker_help_article`, `public_layout_sample`, `expected_output_example` or `explanation_template` as source evidence.
13. Do not use `calculation_template` as raw source evidence without review.
14. Do not use `customer_sample_pending_review` as source evidence.
15. Unsupported or unreadable documents must remain in inventory and create review issues if needed.
16. ZIP archives are conditional until unpack/review is explicitly approved.

## 4. Source Fact Rules

17. Every source fact must have source evidence.
18. `raw_value` must come from visible source evidence or be marked unavailable.
19. `normalized_value` may only perform mechanical normalization.
20. LLM inference without evidence must be `review_only` or `uncertain`.
21. Source facts must not calculate final tax base.
22. Source facts must not decide fee eligibility.
23. Source facts must not decide foreign tax treatment.
24. Source facts must preserve source granularity: document, page, table, row, cell, text excerpt, mixed or unknown.

## 5. Ledger Rules

25. Every ledger item must cite source facts.
26. Ledger `raw_fields` must trace back to source facts.
27. Ledger `normalized_fields` must not include tax-base conclusions.
28. Ledger `calculated_fields` require deterministic calculation trace.
29. A ledger item requiring calculation cannot be `calculated` without trace and validation status.
30. Conflict ledger entries must not silently choose a winner without customer methodology.
31. Calculation trace must name inputs, algorithm/formula id, methodology ref when required and output refs.

## 6. Declaration Model Rules

32. Declaration model v0/v0.1 must not absorb full source rows.
33. Declaration candidates must cite source fact refs or ledger item refs.
34. Every period-aware declaration model must record `tax_year`, `form_year` and `official_source_set_id`.
35. Do not use the 2025 official source set for another tax year without a separate source set or explicit review status.
36. Candidate income code signals remain candidate signals until confirmed for the target period and methodology.
37. Declaration model values requiring deterministic calculation must not be filled from LLM-only totals.

## 7. Methodology Rules

38. Fee eligibility requires customer methodology.
39. Currency conversion completeness requires rate/date policy.
40. Foreign tax treatment requires customer methodology.
41. Income category/code mapping requires customer methodology.
42. Summary/detail precedence requires customer methodology.
43. IIS/non-IIS treatment requires customer methodology.
44. Accepted source-reference granularity requires customer methodology.
45. Missing methodology must be marked `requires_customer_methodology` or `placeholder`.

## 8. Review State And Readiness Rules

46. Readiness must not be interpreted as final tax correctness.
47. Allowed positive readiness is only `ready_for_specialist_review`.
48. `ready_for_filing`, `ready_for_final_tax_result`, `ready_for_auto_declaration` and `ready_for_xlsx_generation` are forbidden.
49. `manual_review_required` must remain true.
50. `tax_correctness_claimed` must remain false.
51. `fns_filing_claimed` must remain false.
52. `xlsx_generation_claimed` must remain false.
53. Blocking issues must be open, answered, resolved or deferred explicitly.
54. Open methodology gaps block any final tax claim.

## 9. Safety And Privacy Rules

55. Raw customer filenames must not appear in safe artifacts.
56. Private local paths must not appear in safe artifacts.
57. Raw account numbers, personal identifiers, addresses, phones and emails must not appear in safe artifacts.
58. Full financial operation rows must not be printed in reports.
59. Customer documents must not be copied into the repository.
60. Customer documents must not be committed.
61. Secrets, keys and environment values must not be read or printed.

## 10. Validation Outcomes

| Outcome | Meaning |
| --- | --- |
| `pass` | invariant satisfied |
| `warning` | non-blocking review note, only if methodology allows it |
| `blocking` | proof cannot advance until resolved |
| `not_applicable` | invariant does not apply to this artifact |

Any safety flag violation is `blocking`.

## 11. Status

```text
CONTRACT_VALIDATION_RULES_READY
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_NEXT_HUMAN_REVIEW
```
