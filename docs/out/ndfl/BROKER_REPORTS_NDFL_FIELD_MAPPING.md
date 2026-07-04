# Broker Reports NDFL Field Mapping

Status: Draft mapping
Date: 2026-07-04
Target contract: `broker_reports_extraction_v0`

## 1. Mapping Rules

Every mapping must preserve:

- source document concept;
- target JSON path;
- evidence wrapper requirement;
- expected source type;
- confidence rule;
- missing/uncertain/conflict behavior;
- question-to-specialist rule.

No field mapping implies final tax correctness.

## 2. Document Manifest Mapping

| Source document concept | Target JSON path | Evidence wrapper requirement | Expected source type | Confidence rule | Missing/uncertain/conflict behavior | Question rule |
| --- | --- | --- | --- | --- | --- | --- |
| Input filename/source label | `document_manifest[].filename` | Not a tax fact wrapper; manifest evidence from upload/prompt context. | `user_pasted_text`, file metadata | High if file metadata exists; medium if user pasted. | Unknown filename becomes synthetic operator label. | Ask for original filename only if needed for review traceability. |
| Container format | `document_manifest[].container_format` | Manifest field. | file metadata or prompt context | High for extension/MIME; medium for pasted text. | Unknown if not provided. | Ask user to confirm original format if ambiguous. |
| Content representation | `document_manifest[].content_representation` | Manifest field. | text layer, table parser, vision/readability notes | High only when proven by parser/runtime; medium in prompt-only. | Raster/mixed uncertainty must be explicit. | Ask for text-readable export if raster blocks extraction. |
| Document type | `document_manifest[].detected_document_type` | Manifest field. | labels, title, section names | High for explicit titles; medium for inferred sections. | Unsupported/unrelated remains in manifest. | Ask what document is if title/sections are unclear. |
| Readability | `document_manifest[].readability_status` | Manifest field. | parser/readability evidence | High if text extracted; low for image-only prompt. | Not readable blocks extraction. | Ask for text-readable copy. |
| Processing mode | `document_manifest[].processing_mode` | Manifest field. | runtime path | High if runtime path known. | Unknown path is not acceptable for proof; mark limitation. | Ask operator/runtime owner to identify path. |

## 3. Taxpayer Mapping

| Source document concept | Target JSON path | Evidence wrapper requirement | Expected source type | Confidence rule | Missing/uncertain/conflict behavior | Question rule |
| --- | --- | --- | --- | --- | --- | --- |
| Taxpayer/client name | `extracted_tax_facts.taxpayer.name` | Required wrapper. | `text_layer`, `table_cell`, `user_pasted_text` | High for explicit label; medium for header-only; low for raster. | If absent, missing if customer methodology requires it. Conflicting names create `conflicts`. | Ask specialist to confirm taxpayer/client identity. |
| Tax identifier | `extracted_tax_facts.taxpayer.tax_identifier` | Required wrapper. | `text_layer`, `table_cell`, `user_pasted_text` | High only when explicit and complete. | Missing by default if absent. Ambiguous/masked identifier is `uncertain`. | Ask for identifier or confirmation that it is intentionally omitted in proof. |
| Broker account ID | `extracted_tax_facts.taxpayer.broker_account_id` | Required wrapper. | `text_layer`, `table_cell` | High for explicit account label; medium for masked/synthetic. | Masked or partial account is `uncertain`. | Ask whether partial account reference is enough for review. |

## 4. Broker Mapping

| Source document concept | Target JSON path | Evidence wrapper requirement | Expected source type | Confidence rule | Missing/uncertain/conflict behavior | Question rule |
| --- | --- | --- | --- | --- | --- | --- |
| Broker name | `extracted_tax_facts.broker.broker_name` | Required wrapper. | `text_layer`, `user_pasted_text` | High for explicit header; medium for help article/context. | Conflicting broker names create `conflicts`. | Ask which broker report should be primary if multiple brokers exist. |
| Report period | `extracted_tax_facts.broker.report_period` | Required wrapper. | `text_layer`, `table_cell` | High for explicit period; medium for inferred date range. | Missing period blocks readiness. Conflicting periods create `conflicts`. | Ask specialist to confirm target tax/reporting period. |
| Report currency | `extracted_tax_facts.broker.report_currency` | Required wrapper. | `text_layer`, `table_cell` | High for explicit currency label; medium if per-row currencies vary. | Multi-currency without conversion rules is `uncertain`. | Ask for methodology on currency conversion/aggregation. |

## 5. Operations Mapping

| Source document concept | Target JSON path | Evidence wrapper requirement | Expected source type | Confidence rule | Missing/uncertain/conflict behavior | Question rule |
| --- | --- | --- | --- | --- | --- | --- |
| Sales total | `extracted_tax_facts.operations.sales_total` | Required wrapper. | `table_cell`, `text_layer` | High only if explicit total or deterministic table aggregate; low if model-calculated from prompt text. | Missing if no sale rows/total found. Uncertain if label ambiguous. Conflict if summary and table disagree. | Ask whether sales rows/summary should drive review. |
| Purchases total | `extracted_tax_facts.operations.purchases_total` | Required wrapper. | `table_cell`, `text_layer` | Same as sales total. | Missing/uncertain/conflict as above. | Ask for purchase/cost basis source if absent. |
| Fees total | `extracted_tax_facts.operations.fees_total` | Required wrapper. | `table_cell`, `text_layer` | High for explicit fees total; medium for fee rows; low for inferred. | Missing if no fees section. Uncertain if fee categories unclear. | Ask whether fees should be included and how. |
| Dividends total | `extracted_tax_facts.operations.dividends_total` | Required wrapper. | `table_cell`, `text_layer` | High for explicit dividend section. | Missing if absent; uncertain if income section mixes types. | Ask for dividend/coupon breakdown if mixed. |
| Tax withheld total | `extracted_tax_facts.operations.tax_withheld_total` | Required wrapper. | `table_cell`, `text_layer` | High for explicit withholding label; low for inferred from net/gross. | Missing/uncertain if not explicit. Conflict if report/tax form disagree. | Ask for source of withheld tax and period. |
| Foreign tax withheld total | `extracted_tax_facts.operations.foreign_tax_withheld_total` | Required wrapper. | `table_cell`, `text_layer` | High for explicit foreign tax label. | Missing if absent; uncertain if country/currency unclear. | Ask for customer methodology and supporting docs. |

## 6. Document Presence Mapping

| Source document concept | Target JSON path | Evidence wrapper requirement | Expected source type | Confidence rule | Missing/uncertain/conflict behavior | Question rule |
| --- | --- | --- | --- | --- | --- | --- |
| Operations table exists | `extracted_tax_facts.documents.has_operations_table` | Wrapper recommended. | `text_layer`, `table_cell` | High if table headers/rows visible. | False/missing if no operations table. | Ask for operations report if needed. |
| Dividends section exists | `extracted_tax_facts.documents.has_dividends_section` | Wrapper recommended. | `text_layer`, `table_cell` | High for explicit section title. | Unknown if mixed income section. | Ask if dividends/coupons exist for period. |
| Tax withholding section exists | `extracted_tax_facts.documents.has_tax_withholding_section` | Wrapper recommended. | `text_layer`, `table_cell` | High for explicit section. | Missing/unknown if not visible. | Ask for tax withholding report if required. |

## 7. Aggregates Mapping

| Source document concept | Target JSON path | Evidence wrapper requirement | Expected source type | Confidence rule | Missing/uncertain/conflict behavior | Question rule |
| --- | --- | --- | --- | --- | --- | --- |
| Per-currency totals | `aggregates.by_currency[]` | Must reference source field wrappers. | `table_cell`, deterministic parser | High only with deterministic aggregation or explicit report total. | Use `uncertain_data` if model-calculated without parser. | Ask for aggregation methodology for multi-currency data. |
| Per-income-type totals | `aggregates.by_income_type[]` | Must reference source field wrappers. | `table_cell`, `text_layer` | High for explicit source totals. | Uncertain if income categories mixed. | Ask for category mapping. |
| Per-document summary | `aggregates.by_document[]` | Must reference document IDs. | manifest/source wrappers | Medium in prompt-only. | Conflict if document summaries disagree. | Ask which document should be authoritative. |

## 8. Missing / Uncertain / Conflicts / Questions

| Source condition | Target JSON path | Rule |
| --- | --- | --- |
| Required field not present | `missing_data[]` | Include field, reason, blocking flag and question ID if blocking. |
| Value present but weak | `uncertain_data[]` | Include candidate values, source refs and reason. |
| Multiple values disagree | `conflicts[]` | Include field, values, source refs and `resolution_status = "needs_specialist"`. |
| Specialist input needed | `questions_to_specialist[]` | Use concise question, priority, related fields and blocking flag. |

## 9. Readiness Mapping

| Condition | Target JSON path | Expected value |
| --- | --- | --- |
| Any run | `readiness.manual_review_required` | `true` |
| Tax correctness | `readiness.tax_correctness_claimed` | `false` |
| FNS filing | `readiness.fns_filing_claimed` | `false` |
| Missing blocking fields | `readiness.status` | `needs_more_data` or `not_ready` |
| Unsupported/raster-only input | `readiness.status` | `not_ready` or `failed` unless Track B experiment is explicitly active |
| JSON proof only | `readiness.can_proceed_to_xls_stage` | `false` by default |

## 10. Customer Methodology Hooks

These rules remain placeholders:

- which fields are mandatory;
- how to treat fees;
- how to treat foreign tax and currency conversion;
- document precedence when sources conflict;
- accepted source-reference granularity;
- when JSON result can progress to later XLS stage.

Mark related decisions as `requires_customer_methodology`.
