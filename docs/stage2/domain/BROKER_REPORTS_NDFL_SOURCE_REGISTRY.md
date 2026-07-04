# Broker Reports NDFL Source Registry

Status: Draft registry
Date checked: 2026-07-04
Scope: sources for Knowledge/test-corpus discovery, not production tax methodology

## 1. Registry

| source_id | title | url | source_type | jurisdiction | language | date_checked | relevance | trust_level | usage_allowed | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `internal_contract_json_v0` | Broker Reports JSON Extraction Contract v0 | ../contracts/BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md | internal_contract | generic | en | 2026-07-04 | prompt_instruction | high | yes | Primary output contract for MVP. |
| `internal_proof_plan` | Broker Reports Document Intake and JSON Extraction MVP Proof Plan | ../proof/BROKER_REPORTS_DOCUMENT_INTAKE_AND_JSON_EXTRACTION_MVP_PROOF_PLAN.md | internal_contract | generic | en | 2026-07-04 | limitation | high | yes | Proof gates and acceptance criteria. |
| `internal_public_artifact_pool` | Public Artifact Pool Research | ../testdata/BROKER_REPORTS_PUBLIC_ARTIFACT_POOL_RESEARCH.md | internal_contract | generic | en | 2026-07-04 | layout | high | yes | Corpus source decisions. |
| `fns_form_3_ndfl_page` | FNS 3-NDFL forms and instructions page | https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/ | official | RU | ru | 2026-07-04 | domain_rules | high | yes | Official source index for forms, filling order and formats. |
| `fns_order_3_ndfl_2025` | FNS order approving 3-NDFL 2025 form/procedure/format | https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/ | official | RU | ru | 2026-07-04 | domain_rules | high | yes | Official form/procedure/format provenance. |
| `fns_blank_3_ndfl_2025_pdf` | FNS blank 3-NDFL form attachment | https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf | official | RU | ru | 2026-07-04 | tax_form | high | yes | Collected as blank form. Use for layout/classification only. |
| `fns_investment_deduction_page` | FNS investment tax deduction page | https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/nalog_vichet/inv_vichet/ | official | RU | ru | 2026-07-04 | domain_rules | high | yes | Use cautiously. It mentions broker agreements/reports as supporting documents; exact extraction logic requires customer methodology. |
| `irs_1099_b_2025` | IRS Form 1099-B 2025 | https://www.irs.gov/pub/irs-prior/f1099b--2025.pdf | official | US | en | 2026-07-04 | tax_form | high | yes | Collected. Layout only; not RU methodology. |
| `irs_8949_2025` | IRS Form 8949 2025 | https://www.irs.gov/pub/irs-pdf/f8949.pdf | official | US | en | 2026-07-04 | tax_form | high | yes | Collected. Transaction form layout only; not RU methodology. |
| `irs_schedule_d_2025` | IRS Schedule D 2025 | https://www.irs.gov/pub/irs-pdf/f1040sd.pdf | official | US | en | 2026-07-04 | tax_form | high | yes | Collected. Negative/related tax form classification. |
| `irs_pub_550` | IRS Publication 550 | https://www.irs.gov/publications/p550 | official | US | en | 2026-07-04 | domain_rules | high | yes | US terms only; not RU methodology. |
| `finra_statement_reader` | FINRA brokerage statement reader | https://www.finra.org/investors/insights/your-brokerage-statement-how-read-and-make-sense-it | educational | US | en | 2026-07-04 | layout | medium | yes | Educational source for common statement sections. |
| `sec_confirmation_bulletin` | SEC confirmation statement bulletin | https://www.sec.gov/investor/alerts/ib_confirmations.pdf | educational | US | en | 2026-07-04 | extraction | medium | unknown | Related transaction-confirmation concepts. |
| `nasaa_statement_brochure` | Understanding Your Brokerage Account Statements | https://www.nasaa.org/wp-content/uploads/2011/08/SIFMA-SIPC-NASAA-Broker-Statements-Brochure.pdf | educational | US | en | 2026-07-04 | layout | medium | unknown | Layout/section reference only. |
| `fidelity_sample_statement` | Fidelity sample portfolio account statement | https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/sample-new-fidelity-acnt-stmt.pdf | public_sample | US | en | 2026-07-04 | layout | medium | unknown | Explicit sample, but not collected due usage/PII-like demo details. |
| `ibkr_model_statement_sample` | IBKR model statement sample | https://www.ibkrguides.com/reportingreference/sample_model_statement.html | public_sample | generic | en | 2026-07-04 | layout | medium | unknown | Explicit HTML sample; index only until usage review. |
| `ibkr_activity_statement_docs` | IBKR activity statement docs | https://www.ibkrguides.com/orgportal/performanceandstatements/statements.htm | broker_help | generic | en | 2026-07-04 | layout | medium | yes | Statement sections and generation concepts. |
| `tbank_read_broker_report` | T-Bank how to read broker report | https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/ | broker_help | RU | ru | 2026-07-04 | extraction | medium | yes | RU help source for header/account/period/operations concepts. Not tax logic authority. |
| `tbank_get_report` | T-Bank broker/depository/tax reports | https://www.tbank.ru/invest/help/educate/broker-report/about/get-report/ | broker_help | RU | ru | 2026-07-04 | extraction | medium | yes | Document taxonomy / availability context. |
| `finam_broker_report_article` | Finam article on broker reports | https://www.finam.ru/publications/item/chto-takoe-brokerskiiy-otchet-i-zachem-on-nuzhen-20221106-234300/ | broker_help | RU | ru | 2026-07-04 | layout | medium | yes | Format expectations only. |
| `bcs_broker_report_faq` | BCS FAQ on reports | https://bcs.ru/faq/category/2/14 | broker_help | RU | ru | 2026-07-04 | layout | low | yes | Retrieval/help context only. |
| `customer_methodology_placeholder` | Customer broker/NDFL methodology | TBD | customer_placeholder | RU | ru | 2026-07-04 | domain_rules | high | unknown | Required before methodology-dependent extraction and readiness. |
| `customer_good_output_placeholder` | Customer expected good output examples | TBD | customer_placeholder | RU | ru | 2026-07-04 | extraction | high | unknown | Required for production acceptance. |

## 2. Not Suitable For Tax Logic

These sources are layout or extraction-only:

- `finra_statement_reader`;
- `sec_confirmation_bulletin`;
- `nasaa_statement_brochure`;
- `fidelity_sample_statement`;
- `ibkr_model_statement_sample`;
- `ibkr_activity_statement_docs`;
- `tbank_read_broker_report`;
- `tbank_get_report`;
- `finam_broker_report_article`;
- `bcs_broker_report_faq`.

## 3. Requires Customer Methodology

Do not finalize rules for:

- mandatory field set;
- source precedence;
- currency handling;
- fee handling;
- foreign tax handling;
- IIS-specific decisions;
- transition from JSON proof to later XLS stage.

All of the above remain:

```text
requires_customer_methodology
```
