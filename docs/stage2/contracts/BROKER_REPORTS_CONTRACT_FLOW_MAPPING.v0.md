# Broker Reports Contract Flow Mapping v0

Status: Maintained flow mapping; global gate placement reconciled
Date: 2026-07-06; ownership reconciled 2026-07-18
Scope: Stage 2 Broker Reports / XLS NDFL contract-to-contract data flow

Canonical gate placement is defined by the
[Broker Reports gate architecture](../blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md).

## 1. Flow

```text
customer folder / safe registry
-> Gate 1 document inventory / DCP / normalized representation
-> Gate 2 source facts / terminal validation / Gate 3 context manifest
-> Gate 3 case assembly / intermediate ledgers
-> Gate 4 declaration model / review state
-> later output artifacts
```

Only safe registry data and existing docs are used in public artifacts. Raw customer documents, raw filenames and private paths stay out of the repository.

## 2. Layer Mapping

| From | To | Fields that move | Refs used | Direct mapping allowed |
| --- | --- | --- | --- | --- |
| safe registry | document inventory | `document_id`, container, MIME/type, technical profile, taxonomy class, safe hashes, case group | `document_id`, `case_group_id` | yes, safe metadata only |
| document inventory | source facts | document eligibility, source granularity, document class | `document_id`, source evidence refs | yes for eligible evidence docs |
| source facts | intermediate ledgers | raw and normalized event facts, dates, amounts, currencies, visible labels, confidence | `source_fact_id`, `document_id` | yes, but no tax-base finalization |
| intermediate ledgers | declaration model | ledger candidates, calculation status, official requirement refs, methodology status | `ledger_item_id`, `official_requirement_refs[]` | conditional |
| Gate 3 case assembly | declaration model | accepted case/ledger refs and, for simple lineage, cited source-fact refs | case-assembly root, `ledger_item_id`, `source_fact_id` | only inside Gate 4; never bypass the Gate 3 scope/reconciliation root |
| declaration model | review state | target paths, readiness gaps, official refs, methodology status | declaration model paths, `official_requirement_refs[]` | yes for issue creation |
| ledgers | review state | calculation gaps, conflicts, unresolved methodology | `ledger_item_id`, `calculation_trace_id` | yes for issue creation |
| review state | later output artifacts | questions, conflicts, readiness summary | `issue_id`, `question_id` | yes, safe review output only |

## 3. Field Movement Rules

### 3.1. Document Inventory To Source Facts

Allowed:

- `document_id`;
- `document_taxonomy_class`;
- `container_format`;
- readability and parser suitability;
- source granularity available;
- safe document hashes.

Not allowed:

- raw filename;
- private local path;
- raw account number;
- full financial row export.

Documents with `can_be_source_evidence = no` cannot produce taxpayer source facts. Official forms and filling instructions can produce official requirement refs, not taxpayer evidence.

### 3.2. Source Facts To Intermediate Ledgers

Allowed:

- `source_fact_id`;
- raw source value;
- mechanically normalized value;
- source date/currency/label;
- source evidence refs;
- confidence and review-only flags.

Not allowed:

- final tax base;
- fee eligibility conclusion;
- withholding treatment conclusion;
- currency conversion marked complete without policy and deterministic calculation.

### 3.3. Intermediate Ledgers To Declaration Model

Allowed:

- `ledger_item_id`;
- normalized event rows;
- deterministic calculation outputs with trace;
- candidate official requirement refs;
- methodology status.

Not allowed:

- LLM-only arithmetic as final values;
- ledger rows copied wholesale into declaration model;
- target candidates without source fact or ledger refs.

### 3.4. Declaration Model To Review State

Allowed:

- missing target model paths;
- official source gaps;
- methodology gaps;
- calculation status gaps;
- readiness blockers.

Review state should reference model paths and issue IDs instead of copying all declaration candidate data.

## 4. Direct Mapping Prohibitions

Do not map directly:

- raw operations rows to final `tax_base_items[]` without ledger and calculation status;
- broker summary totals to final tax base without reconciliation;
- official form layout to taxpayer source facts;
- calculation template values to raw source evidence without review;
- customer sample pending review to source facts;
- `case_group.readiness` from safe registry to final workflow readiness.

## 5. Methodology Gates

Customer methodology is mandatory for:

- pilot tax years and broker/source scope;
- complete package definition;
- income category/code mapping;
- fee eligibility;
- dividend/coupon split;
- foreign tax treatment;
- currency rate source/date policy;
- summary/detail conflict precedence;
- sufficient source granularity;
- readiness criteria.

Until approved, use:

```text
requires_customer_methodology
```

or:

```text
placeholder
```

## 6. Deterministic Calculation Gates

Deterministic calculation is mandatory for:

- lot matching;
- securities gain/loss candidates;
- source table aggregation if used as calculated result;
- currency conversion;
- rate lookup and rounding;
- summary/detail reconciliation;
- duplicate/overlap detection when it affects amounts.

LLM can propose candidates and questions, but cannot mark these calculations complete.

## 7. Cross-Layer Checks

| Check | Between layers | Failure output |
| --- | --- | --- |
| every source fact has evidence | source facts -> document inventory | `missing_data` or `calculation_gap` issue |
| every ledger item has source facts | ledgers -> source facts | `calculation_gap` or `missing_data` issue |
| every declaration candidate has source/ledger refs | declaration model -> ledgers/source facts | `official_source_gap` or `methodology_gap` issue |
| official source set matches period | declaration model -> registry | `official_source_gap` issue |
| fee eligibility has methodology | ledgers -> declaration model | `methodology_gap` issue |
| currency conversion has rate/date policy | ledgers -> review state | `methodology_gap` and `calculation_gap` issues |
| readiness stays specialist-only | review state -> case package | `blocked` case status |

## 8. Later Output Artifacts

Later output artifacts may include:

- safe specialist questions;
- conflict report;
- review summary;
- synthetic proof assertion results.

They do not include XLS/XLSX export, automatic declaration generation or FNS submission in this Stage 2 contract family.

## 9. Status

```text
CONTRACT_FLOW_MAPPING_READY
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_NEXT_HUMAN_REVIEW
```
