# OpenWebUI Broker Reports Knowledge And Test Corpus Discovery Report

Date: 2026-07-04
Scope: discovery pack, public artifact research, domain Knowledge/Prompt/Skill drafts
Runtime changes: none

Outputs:

- [BROKER_REPORTS_PUBLIC_ARTIFACT_POOL_RESEARCH.md](../../stage2/testdata/BROKER_REPORTS_PUBLIC_ARTIFACT_POOL_RESEARCH.md)
- [BROKER_REPORTS_SYNTHETIC_FIXTURES_FROM_PUBLIC_LAYOUTS_PROPOSAL.md](../../stage2/testdata/BROKER_REPORTS_SYNTHETIC_FIXTURES_FROM_PUBLIC_LAYOUTS_PROPOSAL.md)
- [BROKER_REPORTS_NDFL_DOMAIN_KNOWLEDGE_PACK.md](../../stage2/domain/BROKER_REPORTS_NDFL_DOMAIN_KNOWLEDGE_PACK.md)
- [BROKER_REPORTS_NDFL_FIELD_MAPPING.md](../../stage2/domain/BROKER_REPORTS_NDFL_FIELD_MAPPING.md)
- [BROKER_REPORTS_NDFL_REVIEW_CHECKLIST.md](../../stage2/domain/BROKER_REPORTS_NDFL_REVIEW_CHECKLIST.md)
- [BROKER_REPORTS_JSON_EXTRACTION_PROMPT_PACK.md](../../stage2/prompts/BROKER_REPORTS_JSON_EXTRACTION_PROMPT_PACK.md)
- [BROKER_REPORTS_NDFL_EXTRACTION_SKILL.md](../../stage2/skills/BROKER_REPORTS_NDFL_EXTRACTION_SKILL.md)
- [BROKER_REPORTS_NDFL_SOURCE_REGISTRY.md](../../stage2/domain/BROKER_REPORTS_NDFL_SOURCE_REGISTRY.md)

## 1. Sources Studied

Local repository:

- broker reports PRD;
- JSON extraction contract v0;
- proof plan;
- synthetic fixtures plan;
- structured-output modes research;
- broker and documents/OCR/Excel blueprints;
- security/data policy blueprint;
- acceptance/test-data requirements;
- extension-first pattern;
- native capability audit.

Public sources:

- FNS 3-NDFL form/order/instruction pages;
- FNS investment deduction page;
- IRS 1099-B, Form 8949, Schedule D, Publication 550;
- FINRA/SEC/NASAA educational brokerage statement materials;
- Fidelity and IBKR explicit sample/model statement layouts;
- T-Bank, Finam and BCS broker-help pages.

## 2. Public Artifacts Found

Collected safe official blank forms:

- `irs_form_1099_b_2025`;
- `irs_form_8949_2025`;
- `irs_schedule_d_2025`;
- `fns_form_3_ndfl_2025`.

Index-only useful layout sources:

- FINRA brokerage statement guide;
- SEC confirmation statement bulletin;
- NASAA brokerage statement brochure;
- Fidelity sample statement;
- IBKR model statement sample and statement docs;
- T-Bank broker report help pages;
- Finam broker report article;
- BCS broker report FAQ.

Rejected/quarantine:

- public filing attachments that likely contain real documents;
- old educational exhibits with visible account-like/personal details;
- commercial/legal template pages with unclear source authority.

## 3. Safe Downloads

Downloaded only official blank forms:

- `docs/stage2/testdata/public_artifacts/irs_form_1099_b_2025/f1099b--2025.pdf`
- `docs/stage2/testdata/public_artifacts/irs_form_8949_2025/f8949.pdf`
- `docs/stage2/testdata/public_artifacts/irs_schedule_d_2025/f1040sd.pdf`
- `docs/stage2/testdata/public_artifacts/fns_form_3_ndfl_2025/16589324_1.pdf`

Each directory has `artifact.metadata.json`.

No broker sample PDF was downloaded.

## 4. Index-Only Items

Broker samples/help pages were kept `index_only` because they are useful for layout vocabulary but not safe enough to become repo-local corpus without legal/privacy review.

US tax forms were collected only as form layouts and negative/related-document cases. They must not be used as Russian NDFL methodology.

## 5. Rejected / Quarantine Items

Rejected or quarantined due privacy/license/source-risk:

- SEC EDGAR brokerage statement attachment: public but likely a real document.
- CPA Journal brokerage statement exhibit: contains personal/account-like values.
- Amulex template page: not official and not a reliable broker-report source.

## 6. RU-Language Broker Samples

Safe RU-language broker help pages were found.

A safe downloadable RU broker-report sample with explicit public/demo status and no personal/account risk was not found in this pass.

Practical result:

- use RU broker help pages as `layout/extraction` sources only;
- generate synthetic RU broker-report fixtures;
- request customer anonymized reports for production acceptance.

## 7. Layout Patterns Found

Useful patterns:

- broker/report header;
- broker identifiers;
- generated date;
- report period;
- investor/account/IIS block;
- operations/trades table;
- dividends/coupons/income section;
- fees/charges section;
- withheld tax section;
- foreign tax labels;
- cashflow/activity section;
- positions/portfolio summary;
- official tax form fields that should not be mistaken for broker reports.

## 8. Synthetic Fixtures Update

Recommended updates:

- enrich text fixture with header/account/period/operations sections;
- add page-like PDF surrogate;
- add CSV columns for trade date, settlement date, asset, quantity, currency, amount, fee and withheld tax;
- add XLSX summary/operations/dividends/fees sheets later;
- add raster watermark and fail-closed expectations;
- add negative official tax-form cases;
- add expected JSON with missing/uncertain/conflict coverage.

Synthetic identifiers only:

- `Synthetic Person Alpha`;
- `Synthetic Broker LLC`;
- `SYNTH-BROKER-0001`;
- `SYNTH-TAX-ID-000000`;
- `SYN`.

## 9. Knowledge Sources

Suitable for Knowledge after review:

- internal JSON contract;
- internal proof plan;
- internal domain knowledge pack;
- field mapping;
- review checklist;
- source registry;
- FNS official pages/forms for authority and boundaries;
- public broker help pages for layout vocabulary only.

Not suitable as tax logic:

- US tax forms;
- broker help-center pages;
- educational articles;
- sample broker statements.

## 10. Skill Elements

The skill draft contains:

- LLM role;
- scope boundaries;
- processing order;
- document classification;
- evidence-first extraction;
- missing/uncertain/conflict behavior;
- raster/vision experiment behavior;
- specialist questions;
- readiness logic;
- prohibitions on tax correctness, filing and XLS generation.

## 11. Prompt Elements

Prompt pack drafts:

- `/broker_intake`;
- `/broker_classify_documents`;
- `/broker_extract_json`;
- `/broker_find_missing_data`;
- `/broker_detect_conflicts`;
- `/broker_questions_to_specialist`;
- `/broker_readiness_check`;
- `/broker_raster_extraction_experiment`.

They are draft content only and are not loaded into OpenWebUI.

## 12. Customer Inputs Still Required

Required before customer-grade proof:

- current CloudCowork/Claude prompts;
- customer methodology;
- required fields;
- source-reference granularity;
- anonymized broker reports;
- expected JSON outputs;
- later expected XLS/XLSX drafts;
- provider/data policy;
- retention/access policy;
- reviewer role and acceptance process.

## 13. Staging Load Decision

Do not load into production Knowledge.

The pack is ready for human review before staging load.

Staging load can be considered only after:

- customer/owner reviews source registry;
- policy owner approves data boundaries;
- prompts/skill wording is reviewed;
- target OpenWebUI Workspace Model/provider path is selected;
- synthetic-only proof run is scheduled.

## 14. Remaining Risks

- public artifacts do not provide ground truth;
- safe RU broker report samples are not available from this pass;
- customer methodology is still absent;
- source precedence rules are absent;
- table/XLSX parsing remains unproven;
- structured-output pass-through remains unproven;
- raster/vision remains experimental;
- provider/data policy remains a gate for real documents.

## 15. Final Status

Recommended statuses:

- `DISCOVERY_PACK_READY`
- `DOMAIN_CONTEXT_NEEDS_CUSTOMER_METHODOLOGY`
- `READY_FOR_STAGING_LOAD_REVIEW`

Not claimed:

- production Knowledge loaded;
- production prompt/skill loaded;
- tax correctness;
- final 3-NDFL;
- FNS filing;
- XLS/XLSX generation;
- production OCR.
