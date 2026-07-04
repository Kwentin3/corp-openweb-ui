# Broker Reports Synthetic Case Ledger Design

Status: Test corpus design
Date: 2026-07-04
Scope: declaration-oriented synthetic test cases for broker reports

## 1. Purpose

Do not generate synthetic broker reports directly from the extraction JSON contract.

Instead use:

```text
Synthetic economic case ledger
-> generated source documents
-> expected declaration-oriented assertions
-> expected extraction assertions
```

This keeps test truth independent from the model output format.

## 2. Why Not Generate From Extraction JSON

Generating reports directly from `broker_reports_extraction_v0` creates circular proof:

- the expected answer is shaped by the output contract;
- missing/uncertain/conflict behavior is under-tested;
- document layout variation is weak;
- declaration-oriented calculations are hidden;
- errors in source-document generation may exactly mirror errors in expected JSON.

A synthetic case ledger gives one independent economic truth source and allows multiple document/rendering variants.

## 3. What Is A Synthetic Case Ledger

A synthetic case ledger is a neutral test-case model containing synthetic economic facts before documents are generated.

It is not:

- a broker report;
- extraction JSON;
- declaration JSON;
- XLS template;
- real customer data.

It is:

- artificial;
- deterministic;
- source for fixture generation;
- source for semantic assertions.

## 4. Ledger Shape

Suggested top-level shape:

```json
{
  "case_id": "synthetic_case_001",
  "case_version": "v0",
  "synthetic_identity": {},
  "tax_period": {},
  "accounts": [],
  "income_events": [],
  "security_operations": [],
  "fees": [],
  "withholding_events": [],
  "currency_events": [],
  "intended_gaps": [],
  "intended_conflicts": [],
  "expected_declaration_assertions": [],
  "expected_extraction_assertions": []
}
```

## 5. Ledger Facts

| Ledger section | Facts |
| --- | --- |
| `synthetic_identity` | `Synthetic Person Alpha`, `SYNTH-TAX-ID-000000`, residency placeholder, review flags. |
| `tax_period` | year, period code candidate, report-period mismatch cases. |
| `accounts` | `Synthetic Broker LLC`, `SYNTH-BROKER-0001`, IIS marker, account role. |
| `income_events` | dividends, coupons, other income, source, date, gross amount, currency. |
| `security_operations` | buy/sell rows, asset, quantity, trade date, settlement date, currency, fees. |
| `fees` | fee type, source row, amount, currency, eligibility status placeholder. |
| `withholding_events` | withholding source, amount, currency, date, domestic/foreign marker. |
| `currency_events` | source currency, date, synthetic rate, conversion method status. |
| `intended_gaps` | missing tax ID, missing source country, missing currency rate, missing methodology. |
| `intended_conflicts` | summary/table mismatch, period mismatch, withholding mismatch. |

## 6. Generated Source Documents

One ledger can generate:

- text broker report;
- text-layer PDF surrogate;
- CSV operations table;
- simple XLSX workbook later;
- dividend report;
- withholding report;
- raster image with watermark;
- mixed text/raster PDF;
- negative unrelated document.

Each generated document should preserve:

- synthetic watermark;
- document ID;
- generated-from case ID;
- intentional gaps/conflicts metadata.

## 7. Distortions To Inject

Useful distortions:

- missing taxpayer identifier;
- report period differs from tax period;
- summary total differs from operations table;
- fees split across sections;
- dividend currency missing;
- foreign tax shown without country;
- raster-only withholding value;
- duplicated operation row;
- hidden/unsupported XLSX formula placeholder;
- low-quality scan.

## 8. Expected Declaration-Oriented Assertions

Assertions should test semantics, not full JSON equality.

Examples:

- one document is classified as `broker_report`;
- one document is classified as `operations_table`;
- tax period candidate exists but requires confirmation;
- source facts contain all sale rows from CSV;
- dividend event maps to `dividends_and_withholding` candidate;
- fee event is source fact but methodology-required for declaration eligibility;
- foreign currency event requires deterministic conversion;
- conflict is raised for summary/table mismatch;
- readiness is not final declaration readiness.

## 9. Expected Extraction Assertions

Examples:

- every generated document appears in `document_manifest`;
- unsupported/raster documents are listed;
- source facts have document/page/sheet/row refs where available;
- missing tax ID appears in `missing_data`;
- uncertain raster value appears in `uncertain_data`;
- conflict appears in `conflicts`;
- questions include data and methodology questions separately;
- safety flags remain false for tax correctness and FNS filing.

## 10. Validation Strategy

Use layered checks:

1. Source document generation checks.
2. Extraction contract checks.
3. Declaration model mapping checks.
4. Semantic assertions.
5. Specialist review checklist.

Avoid:

- snapshot-only proof;
- equality against full LLM output;
- accepting source facts without evidence;
- accepting declaration targets without methodology.

## 11. Next Step

After human review:

1. Define `synthetic_case_001`.
2. Generate source documents from ledger.
3. Write expected semantic assertions.
4. Run prompt-only extraction proof.
5. Map source facts to declaration model.
6. Record gaps before any XLS/XLSX stage.
