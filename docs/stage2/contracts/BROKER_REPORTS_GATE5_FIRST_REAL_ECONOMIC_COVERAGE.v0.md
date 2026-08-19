# Broker Reports Gate 5 First Real Economic Coverage v0

Status: `HISTORICAL RESEARCH SCAR`; superseded by the G5.40C
[Source-Fact Domain Boundaries](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md).

The former related-event runtime was removed. G5.39/G5.39R showed that exact
structural proximity, dates, asset and whole-quantity equality do not prove
financial-event identity. This document records the rejected boundary; it is
not current runtime authority.

## Outcome boundary

G5.38 may terminate only as `FIRST_REAL_ECONOMIC_COVERAGE_PROVEN` or
`STRATEGIC_STOP`. It does not activate declaration production, claim
taxpayer-wide completeness, support a named broker, submit to FNS or authorize
G5.39.

Current terminal outcome: `STRATEGIC_STOP`.

## Existing owners

- PDF intake remains owned by the existing Gate 1 table detector, Dual-VLM
  runtime and semantic visual migration factory.
- Financial meaning remains owned by the Gate 3 dictionary and role pack.
  `TRANSACTION_CHARGE` already excludes unspecified, account and custody
  charges; no second charge taxonomy was created.
- Financial facts remain owned by
  `Gate4FinancialCaseRuntimeFactory.create`.
- The former `Gate5RelatedSecuritiesEventsRuntimeFactory.create` was the bounded
  experimental relation owner and is no longer present in the product tree.
- The existing trusted securities-disposal methodology, Tax Model,
  declaration, XML projection and OpenWebUI product owners remain unchanged.

## Rejected experimental relation rule

A relation is resolved only when the current private case contains:

1. exactly one role-complete `SECURITY_DISPOSAL`;
2. exactly one earlier role-complete `SECURITY_PURCHASE` with the same asset,
   currency and complete disposed quantity;
3. exactly one role-complete `TRANSACTION_CHARGE` sharing the purchase's exact
   Gate 3 canonical binding and annotation target, date and currency;
4. no second qualifying purchase/charge group.

The rule is whole-quantity only. FIFO, partial-lot allocation, nearest-date
selection, first-match selection and inferred missing values are forbidden.
Purchase-only and ambiguous cases return a typed blocker and create no Tax
Model or XML.

## Tax boundary

The relation supplies acquisition cost and transaction expense to the existing
Article 214.1 paragraph 10 methodology as `related_financial_case` evidence.
It does not itself decide tax deductibility. The trusted Tax Model still owns
the documented, actually incurred and operation-related prerequisite check.

Official methodology evidence remains the Tax Code locator and FNS-hosted
Federal Law No. 281-FZ evidence already pinned by the trusted methodology.

## Proven and stopped surfaces

The official public PDF was processed without broker-specific code. The
qualified profile retained 13 valid regions, rejected two invalid regions and
accepted four literal monetary tables while leaving nine unsupported. One
bounded qualification turn produced two purchase facts and two transaction
charges with complete roles and exact purchase/charge target pairs.

The final clean product-path turn used the published qualification identities
and did not retry. It preserved the four financial labels but the provider
returned every role as `missing`. Gate 4 therefore exposed no role-complete
purchase, and the relation stopped at
`gate5_related_events_purchase_missing`. Reusing the earlier private case was
not possible because its temporary authenticated user had been deleted during
the required cleanup. Re-running the official inference would turn the proof
into best-of-N, so G5.38 stops.

## Next allowed boundary

Only a continuation inside G5.38 may address the row-bound role-context gap.
It must make accepted semantic rows the deterministic Gate 3 role-binding
context and then run one new clean proof. Retrying unchanged provider input,
copying private facts across users/cases, G5.39, production activation and
manual XML repair are not authorized.
