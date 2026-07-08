# Broker Reports Data Contract Family v0

Status: Draft contract family
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL data contracts

## 1. Purpose

This document defines the contract family for the Broker Reports workflow.

The workflow is intentionally layered:

```text
case package
-> document inventory
-> source facts
-> intermediate ledgers
-> declaration-oriented model
-> review state
```

The goal is `ready_for_specialist_review`. This family does not define final tax correctness, automatic 3-NDFL completion, FNS filing, XLS/XLSX generation or OpenWebUI Knowledge loading.

## 2. Why Not One Large JSON

One `everything.json` would mix responsibilities that need different owners, validation rules and safety gates:

- file intake and safe customer-document indexing;
- document taxonomy and technical suitability;
- source-fact extraction from visible evidence;
- deterministic intermediate calculations;
- declaration-oriented target candidates;
- official requirement references;
- customer methodology gaps;
- conflict and readiness review.

The current `broker_reports_extraction_v0` is useful for the first prompt-only proof, but it combines manifest, facts, aggregates, issues and readiness in one output. The next proof needs clearer boundary contracts so that:

- source facts stay evidence-first;
- ledgers can be recalculated deterministically;
- declaration mapping can cite ledgers or facts instead of raw document rows;
- review state can collect blockers without mutating source data;
- customer documents can be referenced by safe IDs without exposing filenames or private paths.

## 3. Contract Family

```text
broker_case_package_v0
  ├─ document_inventory / manifest
  ├─ source_facts_v0
  ├─ intermediate_ledgers_v0
  ├─ declaration_model_v0/v0.1
  └─ review_state_v0
```

| Contract | Owner | Data owned here | Data not owned here |
| --- | --- | --- | --- |
| `broker_reports_case_package_v0_proposal` | case orchestration | `case_id`, status, tax/form year, refs to every artifact, safety flags | raw facts, ledger rows, declaration rows, issue bodies |
| `document_inventory / manifest` | intake and taxonomy | `document_id`, safe hashes, container, MIME, size, readability, taxonomy class, technical suitability, `case_group_id` | source facts, tax-base calculations, final readiness |
| `broker_reports_source_facts_v0_proposal` | evidence extraction | event-level facts, raw/normalized values, source evidence refs, confidence, source granularity | deterministic tax-base calculation, final declaration mapping |
| `broker_reports_intermediate_ledgers_v0_proposal` | calculation-prep and deterministic ledger layer | normalized ledgers, calculation status, methodology status, consistency checks, trace links | official form structure, final declaration assertions |
| `broker_reports_ndfl_declaration_model_v0/v0.1` | declaration-oriented target model | period applicability, official requirement refs, target candidates, model paths | raw source-document inventory, full ledger history |
| `broker_reports_review_state_v0_proposal` | specialist review gate | missing, uncertain, conflicts, gaps, questions, readiness | source evidence extraction, deterministic calculations, filing output |

## 4. Non-Duplication Rules

- The case package stores refs, not full child artifacts.
- Document inventory stores safe metadata and classification, not extracted values.
- Source facts store raw and mechanically normalized facts, not final tax-base results.
- Intermediate ledgers store calculation-prep rows and deterministic calculation status, not final declaration output.
- Declaration model stores target candidates and official requirement refs, not complete source rows.
- Review state stores issues and readiness, not copied facts or ledger rows except small references and labels safe for review.

## 5. Reference Pattern

All contracts use stable refs:

| Ref | Target |
| --- | --- |
| `case_id` | one broker-report case package |
| `case_group_id` | safe registry case group, for example `case_group_002` |
| `document_inventory_ref` | safe document inventory artifact |
| `document_id` | one safe inventory item |
| `source_facts_set_id` | source facts artifact for a case |
| `source_fact_id` | one extracted event/fact |
| `intermediate_ledgers_id` | ledger artifact for a case |
| `ledger_item_id` | one ledger item |
| `declaration_model_id` | declaration-oriented model artifact |
| `official_requirement_refs[]` | records from the official requirements registry |
| `review_state_id` | review state artifact |
| `issue_id` | one missing/uncertain/conflict/gap/question issue |

Refs must be enough to prove traceability without embedding raw customer filenames, private paths or full financial operation rows.

## 6. LLM, Deterministic Calculation And Methodology Boundaries

| Area | LLM can work directly | Deterministic calculation required | Customer methodology required |
| --- | --- | --- | --- |
| Document inventory | classify document role, detect obvious suitability, summarize safe metadata | duplicate detection by hash, parser checks | approval to use customer samples as evidence |
| Source facts | extract visible event facts with source refs | table parsing, numeric normalization where parser-backed | required fields, source precedence, accepted granularity |
| Intermediate ledgers | propose ledger placement and review notes | totals, matching, currency conversion, tax-base math, formula trace | fee eligibility, income code mapping, withholding treatment, rate/date policy |
| Declaration model | propose target candidate paths from ledgers/facts | calculated declaration-currency amounts and tax-base candidates | final mapping policy and readiness criteria |
| Review state | draft questions and classify blockers | consistency checks can feed issue creation | issue severity, acceptable unresolved warnings |

## 7. Extraction Boundary

Source fact extraction ends when the workflow has captured visible document facts with evidence refs:

```text
document_id + source location + raw_value + normalized_value + confidence
```

Declaration-oriented mapping starts when those facts are placed into target model paths or ledgers that depend on official requirements, customer methodology or deterministic calculations.

Examples:

- A sale row from an operations table is a `securities_operation_event`.
- A normalized sale row in `securities_operations_ledger` is still not final tax base.
- A `tax_base_items[]` candidate must cite source facts or ledger items and carry `methodology_status`.
- A fee row can be a source fact, but fee eligibility remains `requires_customer_methodology`.

## 8. Safe Customer Source Index Anchor

The current safe customer source index is:

```text
docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json
```

It can be used by the case package through:

- safe `document_id`;
- safe `case_group_id`;
- document taxonomy class;
- technical profile;
- safe hashes.

It must not be expanded with raw filenames, raw relative paths or private local paths in public artifacts.

## 9. Status

```text
DATA_CONTRACT_FAMILY_DRAFT_READY
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_NEXT_HUMAN_REVIEW
```
