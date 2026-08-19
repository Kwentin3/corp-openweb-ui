# Broker Reports Gate 5 — Declaration Demand Map (G5.40A)

Date: 2026-08-12
Status: `DECLARATION_DEMAND_MAP_PROVEN`

## Outcome

The researched 2025 3-NDFL securities case has a complete backward demand map:

```text
declaration value
→ form/tax rule
→ minimum facts required by that rule
→ official source or explicit MISSING
```

The machine-readable map contains 28 demand rows and accounts for all 48 possible semantic leaves in the current released declaration-value contract, including the two conditional representation-authority leaves. It also accounts for target constants and generated file identity separately.

The result is deliberately bounded to a resident individual, Russian-source disposal of organized-market securities outside an IIS, tax period 2025, with the current inactive payable/single-allocation projection profile. It does not assert real-taxpayer completeness, real-document coverage, or product activation.

## Authoritative form boundary

The current form boundary was reverified on 2026-08-12:

- [FNS Order No. ED-7-11/913@ of 20 October 2025](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/) approves the 3-NDFL form, filling procedure and electronic format used for declarations for tax period 2025.
- [Official form PDF](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf) defines the Title, Sections 1 and 2, Appendix 1 and Appendix 8 fields.
- [Official filling procedure](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx), SHA-256 `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc`, defines when and how those fields are completed.
- [Official XSD 5.20.01](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd), SHA-256 `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484`, defines the electronic target structure.

Relevant current tax rules were checked through the FNS-linked Tax Code publication: [Article 210](https://nalog.garant.ru/fns/nk/6a3eaa02cea3fe2db1e9b04e275d1439/), [Article 214.1](https://nalog.garant.ru/fns/nk/67db01bcbcd5bd5643515ba89437b4c0/), [Article 225](https://nalog.garant.ru/fns/nk/019663de1a1d5400d8d7e472836929d5/) and [Article 226.1](https://nalog.garant.ru/fns/nk/6cd8d3f6905f78365f70b64fb5f0a8a7/).

## Compact demand map

| Declaration demand | Required when | Kind | Rule output and minimum inputs | Source / gap |
|---|---|---|---|---|
| Form/file identity | Every electronic declaration | Constant/generated | Form/version, tax period, generated file ID | Official form/XSD proven |
| Filing, taxpayer and signer | Every declaration; representation only when used | Direct facts plus legal classification | Filing intent/date/authority, authenticated taxpayer, period residence, filing category, signer capacity and authority | Real authenticated case evidence `MISSING`; repository data is synthetic proof only |
| Section 1 budget disposition | After all Section 2 calculations; one row per KBK/OKTMO | Classification plus calculation | Payable/refundable outcome, KBK, OKTMO, complete allocation set | Calculation owner exists; real allocation evidence `MISSING` |
| Section 2 income group and income | One page per applicable group | Classification plus aggregation | Residence, securities/outside-IIS classification, all source income, exemptions and source completeness | Official group `02` / kind `003` rule proven; real inputs/completeness `MISSING` |
| Section 2 deductions and expenses | When applicable; zero requires scoped non-activation | Election plus tax calculation | Claims/losses, Appendix 8 allowable expenses, eligibility, limits and completeness | Expense methodology has one G5.40B gap; real claim/absence evidence `MISSING` |
| Section 2 tax and settlement | Every applicable group; credits only under their conditions | Calculation plus conditional direct facts | Tax base, two-band 13%/15% rule, withholding and every applicable credit, settlement completeness | Formula and bounded owner proven; real settlement evidence `MISSING` |
| Appendix 1 Russian-source rows | Per Russian source and income kind | Direct/source aggregate plus classification | Source identity, kind `003`, gross income, tax-agent status and withholding, complete source list | Real broker/source extraction and coverage `MISSING` |
| Appendix 8 category rows | Per applicable operation category | Classification plus tax calculation | Category `01`, category income, related expenses, allowable expenses, loss treatment and category completeness | Official aggregate fields proven; partial-lot acquisition-commission method remains G5.40B |

The full row-by-row matrix is in `BROKER_REPORTS_GATE5_DECLARATION_DEMAND_MAP_G5_40A.matrix.safe.json`, SHA-256 `763af13747169a4813f87b9a9212bb8ea8303f77ac6393fc106256593c9e1283`.

## Exact backward conclusions

### What the declaration consumes

For the researched case, the declaration consumes:

1. filing/party facts;
2. per-source Russian income rows;
3. one income-group result for group `02`;
4. one or more Appendix 8 category aggregates, with code `01` for the bounded organized-market/outside-IIS case;
5. final settlement and budget-allocation results.

The official procedure states that Appendix 8 line 020 is total income across the category's operations, line 030 is total related expense, and line 040 is total expense accepted in reduction of income. Section 2 then consumes Appendix 8 line 040, plus accepted current-period losses, at line 050.

### What it does not consume

No researched declaration field consumes:

- a universal financial event;
- a transaction graph;
- a purchase-to-sale edge;
- a purchase-commission-to-sale edge;
- document page proximity or a model-inferred relationship.

This is a declaration-bound conclusion only. A tax rule may still require a narrower relation to calculate an aggregate correctly. Such a relation is allowed only if G5.40B proves that the tax rule consumes it.

## Explicit MISSING boundary

The map exposes, rather than fills, these gaps:

- real authenticated filing, taxpayer and signer evidence;
- real KBK/OKTMO allocation evidence;
- real broker/source facts and source/category completeness;
- real evidence for withholding, credits, claims, exemptions and loss history, or a scoped proof that they are not activated;
- legal methodology for the amount/timing of acquisition commission recognized when only part of a FIFO acquisition lot is disposed.

The last item is the nearest legal-methodology question. It is not a reason to fail G5.40A: the required declaration output and the missing rule are now identified exactly.

## Repository fit

The current inactive consumer-first projection has 49 target mappings: 48 attribute mappings plus the taxpayer-INN text mapping. The declaration-value contract exposes 48 possible semantic leaves. The G5.40A matrix covers all 48 with no missing or extra semantic paths.

Existing owners remain the route:

- `filing_and_party_identity`;
- `declaration_budget_disposition`;
- `income_group_tax_results`;
- `taxable_income_by_source`;
- `financial_investment_results`.

No runtime, factory, DTO, event model, relation model, persistence owner or projection activation was added.

## Validation

- Official filling-procedure download hash matched the repository pin exactly.
- Matrix JSON parsed successfully.
- Demand rows: `28`.
- Authoritative sources: `8`.
- Semantic-leaf accounting: expected `48`, actual `48`, missing `0`, extra `0`.
- Matrix SHA-256: `763af13747169a4813f87b9a9212bb8ea8303f77ac6393fc106256593c9e1283`.
- Repository code was not changed; no product test was required for this research-only artifact.

## KISS check

The output is one demand map and one receipt. It reuses the current declaration-value vocabulary and current owners. It adds no speculative financial concept. Every listed input fact is present because a concrete declaration field or tax calculation consumes it.

## Terminal

```text
DECLARATION_DEMAND_MAP_PROVEN
```

Next authorized goal: `G5.40B — Securities expense methodology`.
