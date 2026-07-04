# Broker Reports Public Artifact Pool Research

Status: Discovery research
Date checked: 2026-07-04
Scope: safe public artifacts for `broker_reports_extraction_v0` document intake and JSON extraction tests

## 1. Collection Policy

Use public artifacts only as a test corpus aid. They do not replace customer methodology, anonymized customer samples or expected JSON outputs.

Allowed:

- official blank forms;
- official instructions;
- broker help-center pages;
- educational pages;
- explicit demo/sample layouts with no evidence of real personal data.

Rejected or quarantine:

- real private documents;
- cloud-share/forum/paste/Telegram documents;
- documents with visible real names, addresses, identifiers, account numbers or non-demo financial records;
- materials with unclear public/demo status.

Collection decision:

- `collect`: safe official blank form downloaded under `docs/stage2/testdata/public_artifacts/<artifact_id>/`;
- `index_only`: useful source or layout reference, but not downloaded;
- `reject`: not suitable;
- `quarantine`: potentially useful but must not be used before legal/privacy review.

## 2. Artifact Pool

| artifact_id | title | source_url | source_domain | source_type | license_or_usage_note | download_allowed | local_collection_recommendation | jurisdiction | language | container_format | content_representation | document_type | contains_real_personal_data | contains_real_account_data | pii_risk | tax_logic_relevance | json_extraction_test_fit | raster_vision_test_fit | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `irs_form_1099_b_2025` | IRS Form 1099-B 2025 | https://www.irs.gov/pub/irs-prior/f1099b--2025.pdf | irs.gov | official blank form | Official public prior-year IRS form; use for US tax-form layout only, not RU NDFL methodology. | yes | collect | US | en | pdf | text_layer | tax_form | no | no | none | layout_only | medium | low | Collected as official blank/prior-year form. Useful for label extraction around proceeds, basis, withholding and account-number fields. |
| `irs_form_8949_2025` | IRS Form 8949 2025 | https://www.irs.gov/pub/irs-pdf/f8949.pdf | irs.gov | official blank form | Official public IRS form; use for transaction-form layout only, not RU NDFL methodology. | yes | collect | US | en | pdf | text_layer | tax_form | no | no | none | layout_only | high | low | Collected. Useful for transaction table labels and negative boundary tests. |
| `irs_schedule_d_2025` | IRS Schedule D 2025 | https://www.irs.gov/pub/irs-pdf/f1040sd.pdf | irs.gov | official blank form | Official public IRS form; use for form classification and layout only. | yes | collect | US | en | pdf | text_layer | tax_form | no | no | none | layout_only | medium | low | Collected. Should be classified as tax form, not broker report. |
| `fns_form_3_ndfl_2025` | FNS 3-NDFL form for 2025 reporting | https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf | nalog.gov.ru | official blank form | Official FNS blank form from order page; use as Russian tax-form layout and boundary source. | yes | collect | RU | ru | pdf | text_layer | tax_form | no | no | none | layout_only | medium | low | Collected. It is not a filled broker report and must not imply filing support. |
| `fns_3_ndfl_forms_page` | FNS forms and filling instructions for 3-NDFL | https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/ | nalog.gov.ru | official instruction index | Official source index; download individual files only after confirming blank/instruction status. | unknown | index_only | RU | ru | html/pdf/docx | mixed | instructions | no | no | none | domain_rules | low | low | Source registry item for official form/instruction authority. |
| `fns_order_3_ndfl_2025` | FNS order approving 3-NDFL 2025 form/procedure/format | https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/ | nalog.gov.ru | official order | Official source. Use for source registry and form provenance. | unknown | index_only | RU | ru | html/pdf/docx/xsd | mixed | instructions | no | no | none | domain_rules | low | low | Confirms official attachments and effective period. |
| `fns_investment_tax_deduction_page` | FNS investment tax deductions page | https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/nalog_vichet/inv_vichet/ | nalog.gov.ru | official instruction | Official explanatory source; use only for high-level checklist/source registry. | no | index_only | RU | ru | html | text_layer | instructions | no | no | none | domain_rules | low | low | Mentions broker service agreement and broker reports as supporting documents for investment deduction cases. Requires customer methodology before extraction logic. |
| `irs_pub_550_2025` | IRS Publication 550 | https://www.irs.gov/publications/p550 | irs.gov | official instruction | Official US investment-income publication; not RU methodology. | no | index_only | US | en | html/pdf | text_layer | instructions | no | no | none | layout_only | low | low | Useful only to understand US terms seen in public broker/tax layouts. |
| `finra_brokerage_statement_reader` | FINRA guide: how to read a brokerage statement | https://www.finra.org/investors/insights/your-brokerage-statement-how-read-and-make-sense-it | finra.org | educational | Public educational page. Not a sample document and not RU methodology. | no | index_only | US | en | html | text_layer | instructions | no | no | none | extraction_only | medium | low | Useful glossary/layout source for statement period, account information, holdings, income, fees and transactions. |
| `sec_confirmation_statement_bulletin` | SEC investor bulletin on confirmation statements | https://www.sec.gov/investor/alerts/ib_confirmations.pdf | sec.gov | educational | Public SEC bulletin. Use for transaction-confirmation concepts only. | unknown | index_only | US | en | pdf | text_layer | instructions | no | no | none | extraction_only | low | low | Useful for negative/related-document classification. |
| `nasaa_broker_statement_brochure` | Understanding Your Brokerage Account Statements | https://www.nasaa.org/wp-content/uploads/2011/08/SIFMA-SIPC-NASAA-Broker-Statements-Brochure.pdf | nasaa.org | educational | Public brochure; usage terms not reviewed. | unknown | index_only | US | en | pdf | text_layer | instructions | no | no | none | extraction_only | medium | low | Useful for common brokerage statement sections; not collected. |
| `fidelity_sample_portfolio_statement` | Fidelity sample portfolio account statement | https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/sample-new-fidelity-acnt-stmt.pdf | fidelity.com | public sample | Explicit sample statement, but includes realistic demo names/account-like values; usage terms not reviewed. | unknown | index_only | US | en | pdf | text_layer | broker_report | no | unknown | low | extraction_only | high | low | Good layout reference for portfolio, income and activity sections. Do not collect until usage review approves. |
| `ibkr_model_statement_sample` | Interactive Brokers model statement sample | https://www.ibkrguides.com/reportingreference/sample_model_statement.html | ibkrguides.com | public sample | Explicit HTML sample/model statement. Usage terms not reviewed. | unknown | index_only | generic | en | html | text_layer | broker_report | no | unknown | low | extraction_only | high | low | Good layout reference for activity statement sections. Do not collect until usage review approves. |
| `ibkr_activity_statement_docs` | IBKR Activity Statement documentation | https://www.ibkrguides.com/orgportal/performanceandstatements/statements.htm | ibkrguides.com | broker_help | Public help page; not a sample document. | no | index_only | generic | en | html | text_layer | instructions | no | no | none | extraction_only | medium | low | Useful to understand statement period, activity, archive, sections and custom statements. |
| `tbank_read_broker_report` | T-Bank help: how to read a broker report | https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/ | tbank.ru | broker_help | Public broker help article; not a downloadable demo report. | no | index_only | RU | ru | html | text_layer | instructions | no | no | none | extraction_only | high | low | Useful RU-language field map: header, broker identifiers, investor data, account/IIS, reporting period and operations. |
| `tbank_get_report` | T-Bank help: broker/depository/tax reports | https://www.tbank.ru/invest/help/educate/broker-report/about/get-report/ | tbank.ru | broker_help | Public broker help article; not a safe sample report. | no | index_only | RU | ru | html | text_layer | instructions | no | no | none | extraction_only | medium | low | Useful for document-type taxonomy and PDF report availability. |
| `finam_broker_report_article` | Finam article: what broker report is and why needed | https://www.finam.ru/publications/item/chto-takoe-brokerskiiy-otchet-i-zachem-on-nuzhen-20221106-234300/ | finam.ru | broker_help | Public broker/explanatory article; not a sample document. | no | index_only | RU | ru | html | text_layer | instructions | no | no | none | extraction_only | medium | low | Useful for format expectations: spreadsheet-like formats, XML, PDF. |
| `bcs_broker_report_faq` | BCS FAQ on broker report retrieval | https://bcs.ru/faq/category/2/14 | bcs.ru | broker_help | Public broker help/FAQ; not a sample document. | no | index_only | RU | ru | html | text_layer | instructions | no | no | none | extraction_only | low | low | Useful only for source registry and customer-question wording. |
| `finra_retail_brokerage_application_template` | FINRA retail brokerage account application template | https://www.finra.org/sites/default/files/NewAccountApplicationAllSectionsWordTemplate_Long.pdf | finra.org | official/template | Public template, but unrelated to broker report extraction. | unknown | reject | US | en | pdf | text_layer | unrelated | no | no | none | none | low | low | Negative unrelated-document candidate if manually approved; not collected. |
| `sec_edgar_brokerage_statement_example` | SEC EDGAR brokerage statement attachment | https://www.sec.gov/Archives/edgar/data/1879158/000187915821000001/Brokerage_March2021.pdf | sec.gov | public filing attachment | Public filing, but likely a real document in an EDGAR record. | no | quarantine | US | en | pdf | text_layer | broker_report | unknown | unknown | high | extraction_only | low | low | Do not use. Public availability does not make it safe for this corpus. |
| `cpa_journal_sample_brokerage_statement` | CPA Journal sample brokerage statement exhibit | https://archives.cpajournal.com/2005/905/images/ex4p27.pdf | cpajournal.com | educational sample | Old educational exhibit with visible personal/account-like details. | no | quarantine | US | en | pdf | text_layer | broker_report | unknown | yes | high | extraction_only | low | low | Do not use before privacy/legal review. |
| `amulex_broker_report_template` | Amulex broker report template page | https://amulex.ru/docs/background-documents/other/623.html | amulex.ru | template/commercial | Not official; legal template generation page; usage not clear. | no | reject | RU | ru | html/pdf/docx | unknown | unknown | unknown | unknown | medium | none | low | low | Not suitable as source of truth or corpus input. |

## 3. Collected Files

Collected under `docs/stage2/testdata/public_artifacts/`:

- `irs_form_1099_b_2025/f1099b--2025.pdf`
- `irs_form_8949_2025/f8949.pdf`
- `irs_schedule_d_2025/f1040sd.pdf`
- `fns_form_3_ndfl_2025/16589324_1.pdf`

Each collected directory contains `artifact.metadata.json`.

## 4. Public RU Broker Samples Verdict

Safe RU-language broker-report help pages were found. A clearly safe downloadable RU broker report sample with explicit public/demo purpose and no personal/account risk was not found in this pass.

Therefore:

- RU broker help pages are `index_only`;
- RU downloadable broker reports remain customer-provided/anonymized or synthetic-only;
- synthetic fixtures should imitate RU broker-report layout patterns without copying real personal/account data.

## 5. Layout Patterns Found

Useful public layout patterns:

- broker/report header with broker identity and report generation date;
- investor/account/IIS references;
- statement period;
- operations/trades table;
- income/dividends/coupons sections;
- fees/charges section;
- tax withheld / withholding labels;
- positions/portfolio summary;
- cash movement/activity section;
- tax form transaction table labels;
- blank tax-form fields that should be classified as forms, not broker reports.

## 6. Use In Proof

Use public artifacts for:

- document classification;
- layout vocabulary;
- negative cases;
- field-label discovery;
- source-reference mechanics.

Do not use public artifacts for:

- final tax methodology;
- production acceptance;
- customer-specific field requirements;
- expected JSON ground truth unless paired with synthetic content.
