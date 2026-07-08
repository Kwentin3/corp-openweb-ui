# Broker Reports Case Package Contract v0 Proposal

Status: Case package contract proposal
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL case-level orchestration

## 1. Purpose

The case package is the top-level contract for one Broker Reports case.

It links document inventory, source facts, intermediate ledgers, declaration-oriented model and review state. It must not become one large JSON that duplicates child artifacts.

## 2. Top-Level Shape

```json
{
  "schema_version": "broker_reports_case_package_v0_proposal",
  "case_id": null,
  "case_status": "intake_indexed | source_facts_extracted | ledgers_built | declaration_mapped | ready_for_specialist_review | blocked",
  "tax_year": null,
  "form_year": null,
  "official_source_set_id": null,
  "customer_methodology_status": "missing | partial | approved",
  "document_inventory_ref": null,
  "source_facts_set_ref": null,
  "intermediate_ledgers_ref": null,
  "declaration_model_ref": null,
  "review_state_ref": null,
  "output_artifact_refs": [],
  "safety_flags": {
    "tax_correctness_claimed": false,
    "fns_filing_claimed": false,
    "xlsx_generation_claimed": false,
    "manual_review_required": true
  }
}
```

Optional implementation-friendly expansion:

```json
{
  "case_group_ref": {
    "safe_registry_ref": "docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json",
    "case_group_id": null,
    "document_ids": []
  },
  "artifact_refs": {
    "document_inventory_ref": null,
    "source_facts_set_ref": null,
    "intermediate_ledgers_ref": null,
    "declaration_model_ref": null,
    "review_state_ref": null
  },
  "status_history": []
}
```

## 3. Allowed Statuses

| Status | Meaning | Minimum required refs |
| --- | --- | --- |
| `intake_indexed` | customer package has safe inventory and classification | `document_inventory_ref`, `review_state_ref` if blockers exist |
| `source_facts_extracted` | evidence-backed source facts were extracted from approved documents | `document_inventory_ref`, `source_facts_set_ref`, `review_state_ref` |
| `ledgers_built` | intermediate ledgers exist and cite source facts | `source_facts_set_ref`, `intermediate_ledgers_ref`, `review_state_ref` |
| `declaration_mapped` | declaration-oriented target candidates exist | `intermediate_ledgers_ref` or `source_facts_set_ref`, `declaration_model_ref`, `review_state_ref` |
| `ready_for_specialist_review` | review package is coherent enough for human specialist review | all refs, readiness flags, open issues allowed only by methodology |
| `blocked` | required evidence, official source, methodology or calculation proof is missing | `review_state_ref` |

## 4. Transition Blockers

| From | To | Blockers |
| --- | --- | --- |
| `intake_indexed` | `source_facts_extracted` | raw customer docs not approved for extraction, unsupported/unknown docs not reviewed, no selected `case_group_id`, unsafe filenames/private paths in public refs |
| `source_facts_extracted` | `ledgers_built` | source facts missing evidence refs, source facts not event-level enough, required facts marked uncertain without issue records |
| `ledgers_built` | `declaration_mapped` | deterministic calculation not run where required, fee/currency/withholding policy missing, official requirement refs absent |
| `declaration_mapped` | `ready_for_specialist_review` | unresolved blocking data gaps, methodology gaps not surfaced, readiness claims tax correctness or filing readiness |
| any | `blocked` | safety flag violation, missing required child artifact, period/source-set mismatch |

## 5. Required Refs By Stage

| Stage | Required refs | Notes |
| --- | --- | --- |
| Intake | `document_inventory_ref`, `case_group_id`, `document_ids[]` | Use safe registry IDs only. |
| Extraction | `source_facts_set_ref`, source `document_id` refs | Source facts must cite evidence. |
| Ledger | `intermediate_ledgers_ref`, `source_fact_refs[]` | Ledgers must not be free-floating calculations. |
| Mapping | `declaration_model_ref`, `official_requirement_refs[]` | Period and official source set must be explicit. |
| Review | `review_state_ref`, `issue_id[]` | Readiness remains specialist-review only. |

## 6. Using `case_group` From Safe Registry

The safe registry groups documents into `case_group_id` records. The case package may select one group:

```json
{
  "case_group_ref": {
    "safe_registry_ref": "docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json",
    "case_group_id": "case_group_002",
    "document_ids": ["brdoc_001_example"]
  }
}
```

Rules:

- Use `case_group_id` and `document_id`, not raw filenames.
- Preserve the safe registry's `readiness` as intake evidence, not final workflow readiness.
- Treat `unknown_or_needs_review` and ZIP archives as blockers or conditional inputs until reviewed.
- Do not copy private registry paths into public artifacts.

## 7. Safety Flags

These flags are mandatory and fail closed:

```json
{
  "tax_correctness_claimed": false,
  "fns_filing_claimed": false,
  "xlsx_generation_claimed": false,
  "manual_review_required": true
}
```

If any flag is inconsistent with the case output, `case_status` must be `blocked`.

## 8. Output Artifacts

`output_artifact_refs[]` may reference later review artifacts, for example:

- safe review summary;
- questions-to-specialist export;
- conflict report;
- synthetic proof assertion results.

It must not reference generated XLS/XLSX or declaration filing output in this Stage 2 contract family.

## 9. Status

```text
CASE_PACKAGE_CONTRACT_PROPOSAL_READY
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_NEXT_HUMAN_REVIEW
```
