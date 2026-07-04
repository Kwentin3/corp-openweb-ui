# OpenWebUI Broker Reports Customer Methodology And Synthetic Case 001 Report

Status: CUSTOMER_METHODOLOGY_INTAKE_PACKET_READY
Date: 2026-07-04
Scope: Stage 2 Broker Reports / XLS NDFL docs-only packet

## 1. Constraints Observed

- Code was not changed.
- Runtime was not changed.
- OpenWebUI was not populated.
- Knowledge/Prompts/Skills were not loaded.
- XLS/XLSX was not generated.
- PDF/XLSX source documents were not generated.
- Implementation blueprint was not written.
- Sidecar UI was not created.
- Real customer documents were not used.
- Customer sample documents were not used.
- Secrets, keys and environment values were not read or printed.
- Final tax correctness was not claimed.
- Automatic 3-NDFL completion was not claimed.
- FNS filing was not claimed.

## 2. Documents Studied

- `docs/reports/2026-07-04/OPENWEBUI_BROKER_REPORTS_DECLARATION_ORIENTED_HUMAN_REVIEW_REFINE.report.md`
- `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_METHODOLOGY_INTAKE_CHECKLIST.md`
- `docs/stage2/contracts/BROKER_REPORTS_SOURCE_FACTS_SCHEMA.v0_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_TAXONOMY.v0.md`
- `docs/stage2/domain/BROKER_REPORTS_NDFL_OFFICIAL_REQUIREMENTS_REGISTRY.md`
- `docs/stage2/contracts/BROKER_REPORTS_NDFL_DECLARATION_DATA_MODEL.v0_1_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0_1_PROPOSAL.md`
- `docs/stage2/prompts/BROKER_REPORTS_DECLARATION_ORIENTED_PROMPT_PACK_PROPOSAL.md`
- `docs/stage2/skills/BROKER_REPORTS_DECLARATION_ORIENTED_EXTRACTION_SKILL_PROPOSAL.md`
- `docs/stage2/testdata/BROKER_REPORTS_SYNTHETIC_CASE_LEDGER_DESIGN.md`

## 3. Documents Created

- `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_METHODOLOGY_BRIEF.md`
- `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_METHODOLOGY_INTAKE_PACKET.md`
- `docs/stage2/testdata/BROKER_REPORTS_SYNTHETIC_CASE_001_LEDGER.md`
- `docs/stage2/testdata/BROKER_REPORTS_SYNTHETIC_CASE_001_SOURCE_DOCUMENTS_PLAN.md`
- `docs/stage2/testdata/BROKER_REPORTS_SYNTHETIC_CASE_001_ASSERTIONS.md`
- `docs/reports/2026-07-04/OPENWEBUI_BROKER_REPORTS_CUSTOMER_METHODOLOGY_AND_SYNTHETIC_CASE_001.report.md`

## 4. Customer Methodology Intake And Blockers

The new intake packet converts the technical checklist into a customer-usable packet:

- short customer explanation;
- 15 first-priority questions;
- grouped technical appendix;
- `question_id`, `question`, `why_it_matters`, `blocking`, `expected_answer_type` and `related_model_path` for each question.

The packet directly addresses current blockers:

- pilot tax years;
- broker/country/source scope;
- income category and code usage;
- document completeness;
- IIS/non-IIS handling;
- fee and expense treatment;
- dividends/coupons/withholding;
- foreign tax handling;
- currency rate source and date rule;
- summary/detail conflict precedence;
- sufficient source granularity;
- expected intermediate ledgers;
- `ready_for_specialist_review` definition.

## 5. Synthetic Case 001 And Source Facts Schema

`synthetic_case_001` is based on an independent synthetic economic ledger, not extraction JSON.

The ledger uses:

```text
tax_year: 2025
official_source_set_id: ru_3ndfl_2025_fns_order_2025_10_20
methodology_assumptions_status: placeholder
```

2025 is used only as a synthetic proof year. It is not a customer scope assertion.

The case includes:

- synthetic person with intentionally absent tax identifier;
- one synthetic foreign broker account;
- one buy operation for `SYNTH-A`;
- one related sell operation for `SYNTH-A`;
- one buy fee;
- one sell fee;
- one dividend for `SYNTH-DIV`;
- one foreign withholding event;
- one currency context;
- one intentional missing field;
- one intentional summary/table conflict;
- one fee eligibility methodology gap;
- one currency conversion calculation gap.

The planned proof path is:

```text
synthetic economic ledger
-> generated source documents
-> document taxonomy classification
-> source facts schema events
-> declaration-oriented candidates
-> review state assertions
```

## 6. Placeholder Methodology Assumptions

The following remain placeholders:

- income category/code selection;
- fee eligibility;
- foreign tax treatment;
- currency rate source and date rule;
- account/IIS interpretation;
- conflict precedence;
- source-reference granularity threshold;
- readiness criteria.

All of these remain `requires_customer_methodology`.

## 7. Why Source Documents Are Planned, Not Generated

The task required no PDF/XLSX generation and no use of customer documents.

Therefore the source document work is limited to a plan:

- planned text broker report;
- planned operations CSV;
- planned dividends report;
- planned conflict summary text;
- planned negative 3-NDFL blank form;
- optional later raster, XLSX and mixed text/raster variants.

This keeps the next review focused on roles, gaps and assertions before fixture generation.

## 8. Next Steps

Recommended sequence:

1. Conduct customer methodology session using the intake packet.
2. Approve or defer methodology assumptions.
3. Review `synthetic_case_001` ledger and assertions.
4. Generate synthetic source documents only after review.
5. Run prompt-only staging proof.
6. Record source facts, declaration candidates, gaps and readiness.

## 9. Verification

Docs-only validation performed:

- UTF-8 BOM verification for new markdown/report files.
- Touched-file trailing whitespace scan.
- Touched-file secret-like scan.
- Touched-file no-money marker scan.
- `git diff --check`.

## 10. Final Statuses

```text
CUSTOMER_METHODOLOGY_INTAKE_PACKET_READY
SYNTHETIC_CASE_001_LEDGER_DRAFT_READY
SYNTHETIC_CASE_001_ASSERTIONS_READY
SOURCE_DOCUMENTS_GENERATION_READY_AFTER_REVIEW
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_NEXT_HUMAN_REVIEW
```
