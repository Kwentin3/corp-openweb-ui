# Broker Reports Gate 5 Evidence to Tax Methodology Bridge v1

Status: `CURRENT SUPPORTING CONTRACT`

Goal: `G5.43`

Date: `2026-08-14`

## Authority boundary

Pipeline Gates v1 remains the gate-placement and status authority. This
contract owns the audited handoff between normalized evidence and the
versioned tax methodologies used by the active 2025 broker/securities case.
It does not activate declaration projection, filing or advisory processing.

The immutable methodology authority is
`Gate5TrustedMethodologyAuthorityFactory.create`. The current cross-demand
input contract is:

```text
ru-3ndfl-2025-declaration-input-contract@2026.2-current-authority
```

The corrected income-group settlement resource is:

```text
ru-3ndfl-2025-income-group-settlement-proof@2026.4-audited
```

The superseded `2026.3-experimental` settlement bytes remain independently
resolvable for historical replay and are not selected by current code.

## Invariants

- A source fact preserves what a document says and never adds residence,
  income-source, allowability or tax-agent meaning.
- A methodology declares applicability, typed inputs, operation, official
  authority, output and fail-closed behavior.
- A bridge selects facts by exact type/role/scope and ordinary deterministic
  operations only: `SELECT`, `FILTER`, `ORDER`, `GROUP`, `FIFO`, `SUM`,
  `COMPARE`, `APPLY RULE` and `FAIL CLOSED`.
- No Gate 4 or Gate 5 owner infers purchase/disposal, commission/disposal or
  withholding/income event relations.
- Detail and aggregate assertions are independent. No reconciliation or
  aggregate splitting is performed.
- User input may establish factual identity, presence days, signer capacity,
  filing instance or filing intent. It cannot author residence, income-source,
  expense-allowability or foreign-tax-credit conclusions.
- Runtime does not read legal text or source documents and does not call an
  LLM. Official text is reviewed into a versioned resource first.

## Active demand owners

| Declaration demand | Owner | Methodology binding | Insufficient-input behavior |
| --- | --- | --- | --- |
| filing instance | `Gate5FilingAndPartyIdentityRuntimeFactory.create` | filing-context rule in declaration-input contract | `USER/CASE` |
| taxpayer identity and period status | same component owner | filing-context plus Article 207 residency rule | `USER/CASE`; fail closed on exception/status ambiguity |
| signer and representation | same component owner | signer-context rule | `USER/CASE` |
| budget disposition | `Gate5DeclarationBudgetOutcomeRuntimeFactory.create` | budget-disposition rule | `USER/CASE` after complete settlement |
| Russian-source taxable income | `Gate5DeclarationIncomeSourcesRuntimeFactory.create` | Article 208 dividend/disposal source rules | `SOURCE` or `CONTRACT`; ambiguity remains unresolved |
| foreign-source income and foreign tax | same source component owner | Articles 208, 214 and 232 | literal broker assertion is source evidence; credit needs the exact Article 232 document role/details and authoritative treaty facts |
| securities and derivatives results | `Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create` | source-fact `2026.7-current-authority`, operation `2026.1`, Article 214.1 input rules | exact source or methodology gap |
| income-group tax base | `Gate5IncomeGroupTaxBaseRuntimeFactory.create` | tax-base `2026.2` plus coupon/dividend/market/FX rules | fail closed |
| income-group settlement | `Gate5DeclarationTaxSettlementRuntimeFactory.create` | settlement `2026.4-audited` | fail closed |

All nine active demands are bound by `Gate5RealTaxCaseAssemblyRuntimeFactory`
to the SHA-pinned declaration-input methodology. Inactive Definition demands
remain `NOT_ACTIVATED_FOR_SUPPLIED_CASE`; absence is not converted to taxpayer
absence.

## Source evidence owners

`Gate3MetadataSourceFactRuntimeFactory.create` owns explicitly labelled party,
broker, account, period and identifier observations. The neutral
`REPORTED_ENTITY_TAX_IDENTIFIER` type preserves an explicitly tagged INN while
deliberately withholding taxpayer/broker role meaning.

Gate 4 Financial Case owners preserve financial observations as
`Gate4FinancialCaseFactV2`. `Gate5EvidenceIntakeRuntimeFactory.create` composes
those contracts without reinterpreting them. The deterministic securities
consumer filters source types, validates roles, orders purchases by date,
applies FIFO and binds a direct charge only through exact canonical-table-row
identity.

## Legal authority set

The published declaration-input contract pins reviewed rules to the official
2025 3-NDFL order and current FNS-hosted Tax Code Articles 207, 208, 210, 214,
214.1, 224 and 232. Current securities settlement uses Article 210 paragraph 6
and Article 224 paragraph 1.1: 13 percent through RUB 2.4 million, then RUB
312,000 plus 15 percent above RUB 2.4 million. The five-band Article 224
paragraph 1 schedule is not applicable to that base.

## Exact remaining gaps

Every active unresolved demand and every generated closure action uses exactly
one of five current owner classes:

- `REAL_SOURCE_EVIDENCE_MISSING`: the supplied evidence horizon lacks the
  required literal fact, for example earlier acquisition history;
- `USER_CASE_FACT_MISSING`: identity, factual residence intervals, signer,
  filing instance or budget intent is absent;
- `EXTERNAL_AUTHORITATIVE_FACT_MISSING`: an official rate, treaty/effective
  state or other authoritative external fact is absent;
- `METHODOLOGY_RULE_MISSING`: the reviewed deterministic tax rule is absent;
- `INTERNAL_CONTRACT_OR_PIPELINE_DEFECT`: the source has the value but a
  contract, role binding or normalization path lost it, or no owner is known.

Only the first two classes may produce a user-facing request. The fifth class
always remains an internal action. It is never relabelled as missing user
evidence.

The current legal stops are `LEGAL_INTERPRETATION_REQUIRED` for partial-lot
acquisition-commission allocation and for the exact non-tax sub-kopeck tie rule
at the 3-NDFL field boundary. The runtime keeps exact Decimal values and does no
intermediate rounding. Foreign withholding is not automatically a credit: a
broker report satisfies the Article 232 source-withholding document branch
only when its issuer is the income payment source and the document contains
the required monthly income and tax details, with the required copy and
notarized translation. Treaty applicability and limit remain external
authoritative facts; refund/reversal netting remains a methodology stop.

## Foreign-tax adjustment input boundary (`G5.90`)

The current executable chain ends too early for a foreign-tax adjustment
calculation. `Gate5DeclarationTaxSettlementRuntimeFactory.create` consumes an
already methodology-derived `foreign_tax_credit`; it does not derive that
credit from withholding, refund, reversal or adjustment observations. The
current declaration-input resource requires foreign tax amount/payment date,
supporting documents, translation and the applicable treaty, but publishes no
adjustment/netting rule.

Explicit official rules establish only that Article 232 credit concerns tax
actually paid on foreign income, is treaty-dependent, is claimed for the
income tax period and requires evidence of income kind/amount/year plus tax
amount/payment date. The 2025 3-NDFL form additionally requires country/source,
income and tax currencies, the tax-payment date, the CBR rate for that date,
the foreign tax amount and the calculated credit. Article 81 provides the
general corrected-declaration rule when an error understates tax. None of
these authorities directly defines broker-side refund/reversal/netting,
association evidence, or the exact period treatment of a later adjustment.

The minimum review envelope is therefore:

| Input | Owner | Why the consumer needs it |
| --- | --- | --- |
| foreign income kind, amount, currency, receipt date/year, source and jurisdiction | `SOURCE` evidence; authority role remains unpromoted until proved | scopes the Article 232 claim and the Russian calculation |
| foreign tax amount, currency, payment/withholding date and authority/tax-agent document | `SOURCE` or supplied authoritative evidence | proves the positive actually-paid/withheld candidate |
| explicit adjustment observation: source wording, stated direction/kind if any, amount, currency, date, issuer and provenance | `SOURCE`; may remain `UNMAPPED` | prevents treating a non-payment movement as paid tax |
| explicit association evidence between adjustment, tax payment and income claim | `SOURCE` or authoritative document | required before any pair, netting or period reassignment; proximity/value equality is forbidden |
| applicable treaty and effective/suspension state; CBR rate and nominal for the exact tax-payment date | `EXTERNAL` | controls eligibility/limit and RUB conversion |
| declaration period, filing/correction instance and evidence cutoff | `USER/CASE` | localizes whether an already-filed declaration may be affected without accepting a user tax conclusion |

`WITHHOLDING/PAYMENT_EVIDENCE` versus `ADJUSTMENT_OBSERVATION` is a required
methodology-input distinction because the former can support an Article 232
claim while the latter cannot be silently added to or subtracted from it.
`REFUND`, `REVERSAL` and `OTHER_ADJUSTMENT` are not separately admitted: the
current consumer makes no different reviewed decision among them. Any of them
stops credit derivation pending authoritative treatment and explicit
association evidence. No signed amount, date, adjacency, instrument or same
document placement proves netting.

This boundary does not change the published versioned JSON because its legal
operation is not yet reviewable. The exact terminals are:

```text
FOREIGN_TAX_ADJUSTMENT_METHODOLOGY_GAP_LOCALIZED
METHODOLOGY_LEGAL_INTERPRETATION_REVIEW_REQUIRED
FOREIGN_TAX_WITHHOLDING_VS_ADJUSTMENT_REQUIREMENT_PROVEN
MINIMAL_REVIEW_FACTUAL_ENVELOPE_PROVEN
SOURCE_USER_EXTERNAL_OWNERSHIP_PROVEN
TAX_CONCLUSION_REMAINS_AFTER_GATE4
NO_INFERRED_NETTING_OR_RELATIONS
```

Until reviewed authority defines the adjustment operation, current Gate 3/4
contracts remain unchanged and `UNMAPPED + literal + provenance` is the
fail-closed source state. A future legal-methodology Goal must decide the
effect and timing first; only then may a source-contract Goal rerun admission.

The G5.43 report and safe audit artifact contain the complete Evidence Map,
Methodology Map, Bridge Matrix and Gap Register for the frozen four-document
corpus. Private values remain outside Git.

## Terminal boundary

G5.43 may claim:

```text
EVIDENCE_REQUIREMENTS_CONTRACT_PROVEN
FACT_TO_METHODOLOGY_BRIDGE_PROVEN
DECLARATION_INPUT_CORE_PROVEN
```

It must not claim `TAX_METHODOLOGY_CONTRACT_PROVEN` while any reviewed legal
methodology detail remains unresolved. It must not claim declaration readiness,
projection release, filing readiness or product activation.
