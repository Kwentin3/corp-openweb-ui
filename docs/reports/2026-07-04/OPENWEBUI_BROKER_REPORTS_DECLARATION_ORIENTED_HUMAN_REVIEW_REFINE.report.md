# OpenWebUI Broker Reports Declaration-Oriented Human Review Refine Report

Status: HUMAN_REVIEW_REFINE_READY
Date: 2026-07-04
Scope: Stage 2 Broker Reports / XLS NDFL docs-only refine after human review

## 1. Constraints Observed

- Code was not changed.
- Runtime was not changed.
- OpenWebUI was not populated.
- Customer sample documents were not used.
- XLS/XLSX generation was not performed.
- Implementation blueprint was not written.

## 2. Human Review Gaps Closed

| gap | closure |
| --- | --- |
| Official requirements were described but not period-aware enough. | Added a period-aware official requirements registry with checkable requirement records and source set IDs. |
| Declaration model v0 lacked explicit form/tax-year authority fields. | Added a non-breaking v0.1 proposal with `tax_year`, `form_year`, `form_version`, `official_source_set_id`, `official_requirement_refs` and `period_applicability`. |
| Extraction v0.1 risked becoming too broad. | Added a separate source facts schema proposal for event-level facts. |
| Document roles could still be mixed. | Added document taxonomy with source-evidence, methodology and knowledge-load permissions per class. |
| Prompt/skill proposals did not fully enforce the new source facts and taxonomy split. | Refined prompt and skill proposals to require source facts schema output, official requirement refs and separate gap classes. |
| Customer methodology blockers were implicit. | Added concrete customer methodology intake checklist. |

## 3. Documents Added

- `docs/stage2/domain/BROKER_REPORTS_NDFL_OFFICIAL_REQUIREMENTS_REGISTRY.md`
- `docs/stage2/contracts/BROKER_REPORTS_NDFL_DECLARATION_DATA_MODEL.v0_1_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_SOURCE_FACTS_SCHEMA.v0_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_TAXONOMY.v0.md`
- `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_METHODOLOGY_INTAKE_CHECKLIST.md`

## 4. Documents Updated

- `docs/stage2/prompts/BROKER_REPORTS_DECLARATION_ORIENTED_PROMPT_PACK_PROPOSAL.md`
- `docs/stage2/skills/BROKER_REPORTS_DECLARATION_ORIENTED_EXTRACTION_SKILL_PROPOSAL.md`
- `docs/stage2/contracts/BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0_1_PROPOSAL.md`

## 5. Why Period-Aware Official Registry Is Needed

The previous declaration-oriented refine correctly used 2025 FNS sources. Human review accepted that direction, but the model still needed an explicit guardrail:

```text
tax_year
-> form_year
-> official_source_set_id
-> official requirement refs
```

Without that layer, a 2025 form/code signal could be accidentally reused for another pilot year. The new registry makes each requirement checkable and forces synthetic/staging proof to name the source set it targets.

## 6. Why Source Facts Schema Is Better Than Expanding Extraction v0.1

`broker_reports_extraction_v0` should remain an evidence-first extraction contract. If it also absorbs declaration model fields, event ledgers, methodology decisions and readiness gates, it becomes too broad to verify.

The separate source facts schema keeps responsibilities clear:

```text
extraction contract: document intake and evidence wrappers
source facts schema: event-level facts with source refs
declaration model: period-aware target candidates
review state: gaps, conflicts and specialist questions
```

This supports future synthetic case assertions without snapshot-testing one oversized JSON object.

## 7. How Taxonomy Protects Knowledge And Skill

The taxonomy separates:

- source evidence documents;
- official requirement documents;
- customer methodology documents;
- templates and examples;
- public layout samples;
- synthetic fixtures;
- unsupported or unrelated inputs.

This prevents instruction/template/example documents from becoming source evidence and prevents broker help pages or foreign forms from becoming RU NDFL methodology.

## 8. Remaining Customer Methodology Blockers

Blocked until customer methodology is supplied or approved:

- pilot tax years;
- broker/country/source scope;
- income type coverage;
- final income category/code usage;
- fee and expense treatment;
- dividend/coupon treatment;
- foreign tax handling;
- currency rate source and date rule;
- IIS treatment;
- corporate actions treatment;
- conflict precedence between summary and detailed rows;
- sufficient source granularity;
- expected intermediate ledgers and acceptance outputs.

## 9. Next Step

Recommended next step:

```text
customer methodology intake
-> synthetic_case_001 design
-> synthetic ledger assertions
-> staging proof planning
```

If the customer methodology session is delayed, proceed only with a synthetic case that clearly marks methodology assumptions as placeholders.

## 10. Verification

Docs-only validation performed:

- UTF-8 BOM verified for all touched markdown/report files.
- `git diff --check` returned no whitespace errors.
- Touched-file trailing whitespace scan returned no hits.
- Touched-file secret-like scan returned no hits.
- Touched-file no-money marker scan returned no hits.
- Touched-file status confirms documentation/report-only changes.

Note: `git diff --check` printed Windows LF-to-CRLF working-copy warnings for existing tracked markdown files; these were not whitespace errors.

## 11. Final Statuses

```text
HUMAN_REVIEW_REFINE_READY
PERIOD_AWARE_OFFICIAL_REGISTRY_DRAFT_READY
SOURCE_FACTS_SCHEMA_PROPOSAL_READY
DOCUMENT_TAXONOMY_READY
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_SYNTHETIC_CASE_LEDGER_DESIGN
```
