# Broker Reports Gate 5 Declaration Preparation v0

Status: `HISTORICAL SUPPORTING CONTRACT`

Publication and replay of Human Adapter facts are superseded by
[Gate 5 Human Fact Scope v1](./BROKER_REPORTS_GATE5_HUMAN_FACT_SCOPE.v1.md).
`broker_reports_gate5_user_case_fact_v0` is historical-readable only and is
rejected by the v1 preparation boundary; it is not silently migrated.

Issue #301 found no trusted authenticated case-to-taxpayer binding owner.
Therefore the current product composition fails closed with
`ndfl_trusted_taxpayer_scope_binding_required`; synthetic preparation tests use
explicit fixture refs only. Preparation does not derive, hash or authenticate a
taxpayer scope and cannot activate this route until the missing upstream owner
contract exists.

Program: `G5.41`, additive `G5.78` owner-aware source-gap routing

Date: 2026-08-16

## Outcome boundary

The program prepares the smallest supplied-case declaration scope from trusted
broker evidence, identifies exact required and advisory actions, and replays
deterministically after a typed user fact or a newly normalized document. It
does not release XML or PDF while any required declaration semantics remain
unsupported.

The allowed incomplete-real-case terminal is:

```text
DECLARATION_PREPARATION_WORKFLOW_PROVEN
REAL_EVIDENCE_GAPS_REMAIN
```

`REAL_DECLARATION_CASE_PROVEN` is reserved for a future replay in which every
active demand is resolved through existing trusted component owners and a
sealed target-independent Declaration Semantic Input exists.

## Owners and composition

| Slice | Owner | Exact responsibility |
| --- | --- | --- |
| G5.41A source adapter | `Gate3MetadataSourceFactRuntimeFactory.create` | query active canonical artifacts through `CanonicalReaderFactory.create` and retain only explicitly labelled client/broker/account/period/tax-identifier observations with provenance |
| G5.41A intake composition | `Gate5EvidenceIntakeRuntimeFactory.create` | combine the strict metadata collection with existing Gate 4 financial-fact counts without re-reading or reinterpreting either contract |
| G5.41B | `Gate5ClientEvidenceReviewRuntimeFactory.create` | turn the existing source-fact assembly blockers into quantitative required findings and bounded client-benefit advisories |
| G5.41C | `Gate5DeclarationScopeActivationRuntimeFactory.create` in `gate5_declaration_scope_resolution.py` | select mandatory and intent/evidence-activated demands inside the single declaration-scope owner, from the trusted Full Definition without copying the 25-obligation catalog |
| G5.41D | `Gate5HumanGapClosureRuntimeFactory.create` | group formal findings into minimal typed user, document, external-authority or methodology actions and normalize authenticated answers into typed user/case facts |
| G5.41E | `Gate5DeclarationPreparationRuntimeFactory.create` | compose A-D, expose proven target-independent values, readiness, exact remaining gaps and deterministic replay routing |

The official downstream target owners remain
`Gate5DeclarationSemanticInputRuntimeFactory.create` and
`Gate5FullTargetXmlProjectionRuntimeFactory.create`. G5.41 does not create a
second semantic-input or projection framework.

## G5.41A evidence intake

The bounded metadata fact is a `normalized_source_fact`, not a tax fact. It
retains:

- a stable fact ID;
- one typed metadata meaning used by filing/scope/question consumers;
- the normalized value;
- document, canonical version, node, field path, source refs and matched-text
  hash;
- `tax_meaning_assigned=false`.

Supported bounded meanings are party/client metadata, broker identity,
account/contract identity, statement period, broker address when explicitly
labelled, and explicit broker/taxpayer identifiers. Missing metadata produces
no default fact. Broker identity, country, address or identifier never implies
income-source jurisdiction or taxpayer residency.

Financial ingestion quality is reported independently using existing Gate 4
facts for security, income, commission, withheld-tax and explicit source-total
categories. Declaration resolution counts cannot lower ingestion quality.

Terminal: `EVIDENCE_INTAKE_CONTRACT_PROVEN`.

## G5.41B client-interest review

Coverage is computed from atomic purchase/disposal source facts by the existing
deterministic source-fact consumer. A finding may expose required quantity,
supported prior quantity and minimum missing quantity, but never persists a
purchase-sale relation.

- `REQUIRED_BLOCKER` means the current published methodology cannot produce the
  required result without the named evidence or research.
- `ADVISORY_FINDING` means the case may continue, but the named evidence can
  plausibly support a credit or allowable expense. Every advisory carries a
  concrete client-benefit rationale.

Commission and withholding `DETAIL`, `AGGREGATE` and `HYBRID` assertions remain
independent. Disagreement does not trigger upstream reconciliation.

Terminal: `CLIENT_EVIDENCE_REVIEW_PROVEN`.

## G5.41C scoped activation

Inputs are form, tax period, normalized user intent and evidence-discovered
financial domains. The trusted Full Definition remains the sole obligation and
applicability-policy catalog.

Definition-mandatory domains are always active. Broker/securities intent and
actual security or taxable-income observations activate only the relevant
income and securities demands. Digital assets, investment partnerships,
property, gifts, vehicles and deductions are not activated merely because the
official form defines them.

No current-input absence is converted to `NOT_APPLICABLE`, and supplied-case
scope never asserts real-world taxpayer completeness.

Terminal: `DECLARATION_SCOPE_ACTIVATION_PROVEN`.

## G5.41D exact closure and replay

The search order is normalized document facts, document metadata, other
supplied documents, authoritative external references, then the user or an
additional document. Requests use exactly one closure type:

```text
EXISTING_EVIDENCE
EXTERNAL_AUTHORITY
USER_FACT
ADDITIONAL_DOCUMENT
METHODOLOGY_RESEARCH
OWNER_UNRESOLVED
```

This list is closure/workflow output, not a computation dependency graph. Its
ordering and the presence of a required action do not suppress calculations
whose named consumers do not require that action. In particular, filing
instance and signer actions block their declaration/release consumers, not
independent financial arithmetic.

Known document values are referenced rather than requested again. A user
answer is validated as a typed factual case input or election with
authenticated-user provenance. Income-source jurisdiction, residency,
allowability and other tax classifications are not accepted as user facts;
they require source evidence plus a published methodology owner.
An additional document is never converted directly into a user fact: it is
routed through the ordinary Gate 1 through Gate 4 normalization path. Every
change re-enters `Gate5DeclarationPreparationRuntimeFactory.create`; previous
LLM reasoning is not authority.

When a current source fact exists but a required role is missing, the first
route is `EXISTING_EVIDENCE` review by the existing Gate 3 -> Gate 4 production
owners. When a source value exists but decimal normalization fails, the first
route is the Gate 4 normalization owner. Neither condition is a USER_FACT or an
ADDITIONAL_DOCUMENT request until the source owner separately proves source
absence.

Required actions are exposed in two explicit projections:

```text
user_facing_required_actions
internal_owner_required_actions
```

Only `USER_FACT` and `ADDITIONAL_DOCUMENT` enter the user-facing dialog
projection. `EXISTING_EVIDENCE`, `EXTERNAL_AUTHORITY`,
`METHODOLOGY_RESEARCH` and `OWNER_UNRESOLVED` remain internal owner work. An
unknown source-blocker owner is `OWNER_UNRESOLVED`; it is never converted to a
document request.

LLM input contains formal findings/actions, not raw transactions. The LLM may
explain or order requests and normalize an answer, but cannot close a blocker,
calculate tax or alter methodology.

Terminal: `HUMAN_GAP_CLOSURE_LOOP_PROVEN`.

## G5.41E readiness and target gate

Readiness exposes active/resolved/blocked demand counts, advisories, exact
methodology bindings and supporting source/metadata counts. The machine-readable
draft contains only actually derived values and omits every unproven value.

XML/PDF release remains closed until a complete sealed Declaration Semantic
Input exists. Target layout is not allowed in source facts, calculations or the
partial declaration draft.

Terminal: `DECLARATION_PREPARATION_WORKFLOW_PROVEN` plus the applicable real or
control evidence terminal.

## Non-goals

No transaction graph, financial-event ontology, generic relation/risk/workflow
engine, reconciliation engine, new TaxCase database, new persistence platform,
universal questionnaire, broker-specific tax rule, direct SQL, provider tax
decision, manual XML, product activation or taxpayer-completeness claim is
authorized by this contract.
