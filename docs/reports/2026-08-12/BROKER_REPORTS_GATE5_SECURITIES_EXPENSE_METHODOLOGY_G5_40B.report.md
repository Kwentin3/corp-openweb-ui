# Broker Reports Gate 5 — Securities Expense Methodology (G5.40B)

Date: 2026-08-12
Terminal: `STRATEGIC_STOP_LEGAL_AUTHORITY_GAP`

## Outcome

The declaration-facing methodology is proven for purchase price, FIFO, direct sale fees, direct broker/exchange fees, custody/depositary fees and cross-income-type shared expenses.

One requested amount is not legally proven from the bounded current official corpus:

> the portion and recognition timing of an acquisition commission when an ordinary securities acquisition is only partially disposed.

The implementation may not substitute a convenient pro-rata formula. G5.40B therefore ends at the authorized strategic stop and does not open G5.40C.

## Direct answer to the special question

Question: must acquisition commission be allocated over a partially disposed FIFO lot, or was the earlier question wrong?

Answer:

- The earlier **declaration relation** question was too broad. The 3-NDFL declaration consumes Appendix 8 category aggregates, not a `purchase ↔ commission ↔ sale` event or graph.
- The **tax-recognition amount** question was valid. Current official authority proves that acquisition-related professional fees can be eligible, but it does not prescribe whether an acquisition commission on a partial ordinary disposal is fully recognized, quantity-pro-rated, carried with FIFO, or handled by another method.
- Therefore the authoritative answer is neither `YES` nor `NO`; it is `NO_AUTHORITATIVE_YES_OR_NO_FOUND`.

## Declaration boundary

The [official 2025 3-NDFL filling procedure](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx), SHA-256 `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc`, requires Appendix 8 category totals:

- line 020 — total income across operations in the category;
- line 030 — total acquisition/disposal/storage/redemption-related expense;
- line 040 — total expense accepted in reduction of category income.

Section 2 line 050 then consumes Appendix 8 line 040 plus accepted current-period losses. No declaration field consumes a transaction graph or a commission-to-sale link.

## Controlling official rules

### Eligibility and level

[Article 214.1(10)](https://nalog.garant.ru/fns/nk/67db01bcbcd5bd5643515ba89437b4c0/) recognizes documented and actually incurred expenses connected with acquisition, disposal, storage and redemption. The express list includes professional-participant services, reimbursed professional-participant expense and exchange fees.

[Article 214.1(12)](https://nalog.garant.ru/fns/nk/67db01bcbcd5bd5643515ba89437b4c0/) defines financial result as income less corresponding expenses. An expense that cannot be directly attributed to an operation class or income type is allocated by the income share of each type. If the corresponding type has no income in the expense period, recognition waits until that income is recognized.

This proves a category/tax-period route for shared expenses. It does not require a link to an individual sale.

### Purchase price and partial quantity

[Article 214.1(13)](https://nalog.garant.ru/fns/nk/67db01bcbcd5bd5643515ba89437b4c0/) expressly applies FIFO to expense **in the form of securities acquisition cost**. That proves consumption of the oldest acquisition quantities and their purchase price.

The same paragraph expressly supplies a proportional rule for a different case — partial redemption of a security's nominal value. It does not supply an equivalent rule for professional-service commission on an ordinary partial quantity disposal. The explicit special rule cannot be generalized without authority.

### Evidence connection

[Article 226.1(4)](https://nalog.garant.ru/fns/nk/6cd8d3f6905f78365f70b64fb5f0a8a7/) requires documentary proof of acquisition/storage expenses incurred outside the tax agent, including transaction/title, payment and amount evidence.

[FNS Order No. ED-7-11/1015@](https://www.nalog.gov.ru/rn77/about_fts/docs/15504229/) requires broker-to-broker information to include acquisition dates and acquisition/storage expenses in relation to each security. Its official attachment was downloaded and verified at SHA-256 `42d26c2106883d8da87468008af9ea6a0a44e7410b2a719183b3e520dc0a46b1`.

That proves an acquisition/security evidence connection. It does not specify a per-unit commission amount, a partial-disposal formula, or a commission-to-sale edge.

### Current corroboration

[FNS guidance dated 7 March 2025](https://www.nalog.gov.ru/rn11/news/smi/15956801/) confirms that securities income is reduced by acquisition, disposal, storage and redemption expenses. [Archived FNS guidance](https://www.nalog.gov.ru/rn78/ifns/imns78_05/info/11815510/) also confirms the commission classes and operation/category result boundary; it is corroborative only, while the current Code text controls.

## Methodology matrix

| Expense | Count? | When | Amount | Level | Required relation | Result |
|---|---|---|---|---|---|---|
| Purchase price | Yes | On disposal | Oldest acquisition cost consumed by sold quantity under FIFO | Security + ordered acquisition lot | Same security, chronology and quantities | `PROVEN` |
| Acquisition commission, full associated quantity disposed | Yes if documented/incurred/connected | With corresponding income | Full documented commission associated only with the fully consumed acquisition | Acquisition/security → category | Commission-to-acquisition/security evidence | `PROVEN_BOUNDED` |
| Acquisition commission, partial associated quantity disposed | Eligible in principle | Unresolved | Unresolved | At least acquisition/security | Acquisition/security is proven; disposed-quantity allocation is not | `LEGAL_AUTHORITY_GAP` |
| Sale commission | Yes if documented/incurred/connected | With disposal income | Full amount attributable to the disposal | Disposal → category | Narrow fee-to-disposal source evidence | `PROVEN` |
| Direct broker/exchange fee | Yes if documented/incurred/connected | With corresponding operation/type | Full direct amount | Operation or income type → category | Only source-proven direct scope | `PROVEN` |
| Custody/depositary fee direct to one income type | Yes if documented/incurred/connected | In a period with corresponding income; otherwise deferred | Full direct type amount | Income type/category + tax period | Service-to-security/type; no sale edge | `PROVEN` |
| Shared fee not attributable to one income type | Yes if documented/incurred/connected | Period end or last-agent contract end; no-income type deferred | Proportional to each type's income share | Income type/category + tax period | Fee to participating types only | `PROVEN` |
| Unclassified/unlinked charge | No until proven | — | — | Unresolved | Do not invent | `FAIL_CLOSED` |

The exact machine-readable matrix is `BROKER_REPORTS_GATE5_SECURITIES_EXPENSE_METHODOLOGY_G5_40B.matrix.safe.json`, SHA-256 `0435489ca535825e2435214099e71eeff516c1b46f3af7c3fb4bb7918027b3d6`.

## Rejected weaker answers

The following outputs would be manual semantic repair and are forbidden:

- `commission × disposed quantity / acquired quantity`;
- full acquisition commission on the first partial sale;
- applying FIFO to commission merely because FIFO applies to acquisition cost;
- treating acquisition commission as an unrestricted category-period expense whenever the category has any income;
- creating a purchase/commission/sale event to hide the missing legal formula.

All four may be implementable conventions. None was found as a current official prescription for the scoped individual NDFL case.

## Minimal relation conclusion

The proven rules require only narrow relations:

- purchase price: same security + ordered acquisitions + quantities for FIFO;
- direct sale fee: source-evidenced fee → disposal;
- acquisition fee: source-evidenced fee → acquisition/security;
- shared fee: fee → participating income types/category.

No universal event identity is required. The unresolved acquisition-commission rule prevents us from deciding whether an additional partial-quantity allocation relation is legally necessary.

## Bounded official-source search

The bounded search covered `nalog.gov.ru`, the FNS-linked current Tax Code, `minfin.gov.ru`, and `cbr.ru`, using combinations of acquisition commission, partial disposal, FIFO, proportional quantity allocation and broker expense-transfer data. No current official rule or binding clarification prescribing the ordinary partial-disposal commission amount was found. Secondary non-official materials were not used as authority.

## KISS check

The result retains one tax-methodology boundary and the declaration's existing category aggregates. It adds no DTO, graph, event, relation engine, persistence, reader or activation path. The only refused step is the one whose legal formula is missing.

## Scope stop

No code or test was changed. No Gate 4 boundary, tax owner, declaration owner, projector, persistence, push, PR or product activation was changed.

G5.40C is not opened because the requested expense methodology remains legally incomplete.

## Terminal

```text
STRATEGIC_STOP_LEGAL_AUTHORITY_GAP
```

Blocker: `PARTIAL_ACQUISITION_COMMISSION_RECOGNITION_NOT_PRESCRIBED`.
