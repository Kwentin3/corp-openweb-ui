# Broker Reports Gate 5 External Evidence Routing v0

Status: `EXPERIMENTAL_G5_11_CONTRACT`

Goal status: `G5.11_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Purpose

This contract proves one bounded route for a declaration-required input that
is not asserted by the Financial Case and is correctly obtainable from an
authoritative external source:

```text
closed required input
-> current Gate 4 read/audit
-> minimal agent-visible research request
-> structured claim plus authoritative evidence bytes
-> deterministic acceptance
-> separate external reference fact
```

The representative input is the 2025 Russian resident securities-income group
`02` rate schedule. This is Reference Data. It is not a broker-document fact,
user-provided Supplemental Fact or Tax Methodology-derived result.

## Candidate selection

The preferred organized-market-status candidate was rejected for this proof.
The current representative Financial Case exposes synthetic asset label
`ACME`, not a stable ISIN or equivalent identifier. Targeted external entity
resolution therefore cannot be proven without inventing identity.

The selected rate schedule is required by the declaration-driven G5.10 trace,
is keyed by a closed period/status/income-group context and is stated by an
official FNS source with applicable-period semantics.

## Sole owner

`Gate5ExternalEvidenceRuntimeFactory.create` is the only G5.11 runtime
entrypoint. It composes `Gate4FinancialCaseRuntimeFactory.create` for the
read-only Financial Case audit.

It owns only:

- validation of one closed external-evidence requirement;
- construction of one minimal research projection;
- deterministic binding of a structured proposal to supplied evidence bytes;
- accepted/rejected/unresolved result projection.

It does not fetch the web, call a provider, persist a fact, apply a tax rate or
write to Gate 4.

## Closed requirement

```json
{
  "schema_version": "broker_reports_gate5_external_evidence_requirement_v0",
  "requirement_id": "ru-ndfl-2025-group-02-rate-schedule",
  "fact_key": "resident_securities_income_group_rate_schedule",
  "entity": {
    "jurisdiction": "RU",
    "tax_period": "2025",
    "income_group_code": "02",
    "taxpayer_status": "resident_individual"
  },
  "declaration_binding": {
    "form": "3-NDFL",
    "knd": "1151020"
  }
}
```

Any other period, group, status, form or fact key fails closed. This is a
one-fact proof, not a reference query language.

## Routing result

`prepare(requirement, context)` reads the current Financial Case only through
Gate 4 and returns:

- `required_fact_status = not_asserted`;
- a hash of the exact current fact set for audit;
- `route = external_authoritative_research`;
- the minimal research request and its canonical SHA-256.

If a future Gate 4 fact unexpectedly contains a role named like this tax
reference fact, preparation fails with
`gate5_external_evidence_gate4_semantic_drift`; it does not accept the role as
silent enrichment.

## Exact agent-visible request

The agent sees only:

```text
schema_version
research_question
required_fact
entity
effective_context
source_policy
required_output
```

It does not see Financial Case facts, asset label, trusted user/case/run scope,
artifact refs, Supplemental Facts, methodology bytes or conversation history.

The one-proof source policy permits only HTTPS evidence from:

```text
nalog.gov.ru
www.nalog.gov.ru
publication.pravo.gov.ru
```

with authority class `tax_authority_primary` or
`official_legal_publication`. Model memory and search snippets are explicit
non-fallbacks.

## Structured proposal

The proposal uses strict schema
`broker_reports_gate5_external_evidence_proposal_v0` and contains:

```text
action = propose_fact | unresolved
research_request_sha256
claim or null
evidence_refs[]
conflicting_values[]
unresolved_reason or null
```

The claim contains the entity and a closed progressive-rate value shape. Each
evidence ref contains authority class, exact URL, source document identity,
content SHA-256, locator, supported claim aspect and effective period.

Raw evidence bytes are passed separately as
`Gate5ExternalEvidenceDocument`. They are not model authority and are not
stored by this boundary.

## Deterministic acceptance

`accept(...)` verifies mechanically:

- closed request/proposal shapes and exact request binding;
- exact fact/entity binding;
- HTTPS host and authority-class policy;
- uniqueness and presence of evidence documents;
- SHA-256 of the actual supplied bytes;
- effective-period coverage of tax period 2025;
- support for both claim value and effective period;
- absence of conflicting values;
- canonical Decimal fields and arithmetic consistency of the threshold amount.

The validator does not pretend to re-perform semantic legal research with
regexes. The research agent proposes the meaning; accepted authority comes
from the bound official evidence, not from the model.

## Accepted external fact

An accepted result contains a deterministic `g5ext_...` reference and:

```text
source_kind = external_authoritative_evidence
evidence_class = externally_verified_reference
derived_tax_conclusion = false
```

It preserves the research request hash, proposal hash, source URLs, locators,
effective context and actual evidence-byte hashes.

The fact says only what the official source establishes for the named group
and period. Applying this schedule to a case or mapping an instrument property
to a declaration operation code remains Tax Methodology behavior.

## Fail-closed outcomes

- `unresolved`: the agent reports insufficient/ambiguous authoritative proof;
  no fact is created.
- `rejected`: request/entity/hash/effective/source/conflict checks fail; no fact
  is created.
- malformed contract input raises a closed G5.11 error before acceptance.

No rejected or unresolved result becomes a Supplemental Fact.

## Persistence

G5.11 returns an immutable, hash-bound structured result but does not persist
it. Existing G5.3 persistence is intentionally not reused because
`user_provided_supplemental` and `externally_verified_reference` are different
provenance classes.

A future replay owner may be justified only after a calculation consumes this
fact. That owner/persistence slice is outside G5.11.

## Non-goals

G5.11 does not add:

- generic research/search/browser orchestration;
- provider transport or retry/fallback;
- source registry or universal whitelist;
- Reference Data service/DB/cache;
- Tax Context or Tax Model;
- methodology execution or tax conclusion;
- Human-in-the-loop fallback;
- Gate 4 field or role enrichment;
- product activation.
