# Broker Reports Gate 5 Declaration-Driven Tax Model v0

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.13_CLOSED`

Proof outcome: `PROVEN_WITH_EXPLICIT_PROOF_ASSUMPTIONS`

Product status: `INACTIVE PROOF`

Date: 2026-08-09

Updated: 2026-08-22 (`G5.40D` source-fact seam; Issue #293 inactive
current-Fact-v2 operation composition)

## Purpose

This contract owns one narrow deterministic semantic boundary:

```text
trusted methodology reference
+ trusted case context
+ source-tagged resolved non-document inputs
        -> Securities Disposal Tax Model V0
        -> G5.12 consumer semantics
        -> existing Appendix 8 fragment
```

It proves that current Gate 5 inputs can form the stable meanings required by
the existing declaration consumer. It does not calculate annual tax base,
rate, tax, or a complete declaration.

## Public boundary and reused owners

The sole construction entrypoint is:

```python
Gate5SecuritiesDisposalTaxModelRuntimeFactory(...).create()
```

Its runtime exposes one inactive proof method:

```python
runtime.run(
    methodology_ref=...,
    resolved_inputs=...,
    context=trusted_artifact_access_context,
)
```

G5.14 adds one compatible operation-only method on the same runtime:

```python
runtime.run_operation(
    methodology_ref=...,
    resolved_inputs=...,
    context=trusted_artifact_access_context,
)
```

`run_operation` returns the reviewed operation classification, money,
expense decisions, loss state and provenance, but does not claim category
completeness and does not call the declaration projector. The original `run`
contract and result remain unchanged.

G5.40D adds one compatible factory-owned source-fact method on the same
runtime:

```python
runtime.run_from_current_source_facts(
    methodology_ref=...,
    source_fact_methodology_ref=...,
    resolved_inputs=...,
    disposal_fact_id=...,
    context=trusted_artifact_access_context,
)
```

The method invokes the deterministic source-fact consumer composed by the
factory. It accepts no caller-supplied consumption payload. Its money inputs
are complete current Gate 4 facts selected under the G5.40D proof-only
methodology; the Tax Model and declaration result contracts remain unchanged.

Issue #293 adds one narrower additive factory seam on the same owner:

```python
factory.create_current_source_fact_operation(
    source_fact_consumption=OrdinaryTradeCandidateRuntimeFactory(...).create(),
)
runtime.run_operation_from_current_source_facts(...)
```

The specialized runtime composes only the trusted methodology authority and
the supplied factory-built Fact v2 consumer. It does not construct
Supplemental Fact discovery or declaration projection, accepts no caller-built
consumption payload, and returns the exact validated consumption result beside
the existing operation Tax Model. It remains inactive/shadow and introduces no
new Tax Model behavior or calculation owner.

The factory composes existing owners rather than bypassing them:

- `Gate5TrustedMethodologyAuthorityFactory.create` resolves exact
  repository-owned methodology bytes;
- `Gate5SupplementalFactDiscoveryRuntimeFactory.create` obtains the current
  Financial Case and persistent Supplemental Fact values through the G5.5
  boundary;
- `Gate5DeterministicSourceFactConsumptionRuntimeFactory.create` owns the
  additive G5.40D normalized-source-fact input path;
- `Gate5DeclarationProjectionRuntimeFactory.create` owns all
  declaration-specific paths, attributes, codes, transforms, and evidence.

The Tax Model runtime does not import Gate 4, Supplemental Fact storage,
ArtifactStore/Resolver, SQL, source readers, model clients, or network clients.

## Trusted methodology

The additive G5.13 identity is:

```text
methodology_id      = ru-ndfl-securities-tax-model-proof
methodology_version = 2026.0-experimental
behavior_id         = securities_disposal_tax_model_v0
```

It is the package resource:

```text
gate5_tax_methodology.ru_ndfl_securities_tax_model_proof.v0.json
```

The existing G5.8 authority map binds that identity and schema to one exact
raw-resource SHA-256. The caller supplies no methodology content, rule,
requirement, behavior, path, or hash.

For the G5.14 operation-only seam the same methodology ID has an additive,
separately hash-pinned version:

```text
methodology_version = 2026.1-experimental
behavior_id         = securities_disposal_operation_tax_model_v0
```

Its applicability rule deliberately omits category completeness. This avoids
turning a single complete operation model into a false complete-category
claim. The G5.13 `2026.0-experimental` package bytes and legacy proof remain
immutable.

The methodology owns:

- the three money-input bindings and four G5.5 requirements;
- the required operation/context values for the reviewed category;
- the resulting stable category;
- one allowability rule for acquisition cost and one for the
  professional-participant transaction fee;
- the legal evidence references behind those rules.

The runtime contains one reviewed behavior implementation. An unknown
behavior fails closed; unreviewed methodology-byte or rule changes fail the
existing raw-resource hash pin.

## Bounded expense evidence

The reviewed rule is based on Tax Code Article 214.1 paragraph 10: a
securities expense must be documented, actually incurred, and related to the
operation. The same provision identifies acquisition payments and services
of professional securities-market participants among the relevant expense
classes.

The repository resource records two primary authority locators, verified on
2026-08-09:

- the consolidated Tax Code Part Two text on the
  [Official Internet Portal of Legal Information](https://pravo.gov.ru/proxy/ips/?docbody=&nd=102067058),
  Article 214.1 paragraph 10;
- [Federal Law No. 281-FZ dated 25.11.2009](https://www.nalog.gov.ru/rn77/about_fts/docs/3897104/)
  and the [official attached text](https://www.nalog.gov.ru/html/docs/281_fz.rtf),
  Article 2 replacement text for Article 214.1 paragraph 10.

The downloaded official RTF was `766722` bytes with SHA-256
`7246df15386c36a3bc0ffee3699aacc1edef752a7f8e442b058de204a3f1a417`.
The consolidated portal entry is recorded honestly as a verified locator,
without a captured-byte claim.

This is a bounded methodology proof, not legal advice or a claim that every
possible fee is allowable. Each component must separately satisfy all three
source-tagged evidence flags.

## Closed resolved-input contract

`broker_reports_gate5_securities_disposal_resolved_inputs_v0` contains only:

- `subject_ref`;
- operation properties: operation kind, organized-market status, IIS status;
- minimal tax context: period, residency, exemption applicability, explicit
  loss treatment;
- explicit category-scope completeness;
- three evidence flags for each of the two expense components.

Every non-document value has:

```json
{
  "value": "<closed scalar>",
  "provenance": {
    "source_kind": "proof_assumption | user_verified_fact | external_authoritative_evidence",
    "source_ref": "<stable resolved-input reference>",
    "input_channel": "<operation | tax-context | scope | expense-evidence>"
  }
}
```

The representative proof uses `proof_assumption` for every such value because
this goal does not prove their production acquisition paths. Money values keep
the original G5.4/G5.5 Financial Case or Supplemental Fact provenance.

## Tax Model V0 meaning

`broker_reports_gate5_securities_disposal_tax_model_v0` contains:

- calculation subject, period, residency, exemption applicability, and an
  explicit complete-category-scope binding;
- full trusted methodology/resource/projection and behavior bindings;
- explicit operation kind and a methodology-derived stable category with all
  classification prerequisites and provenance;
- category gross income with Financial Case sources and completeness
  derivation;
- related expense components and Decimal total;
- a separate methodology eligibility decision for each expense component,
  including rule, legal evidence refs, prerequisites, failed prerequisites,
  and methodology projection hash;
- allowable components and a separately computed Decimal total;
- explicit loss treatment and its provenance;
- a sorted audit list of every proof-only assumption.

The model has no 3-NDFL path, Russian attribute name, declaration code, tax
rate, tax amount, group-02 tax base, or old G5.7 `net_result` meaning.

## Expense separation

Relatedness and allowability are deliberately distinct:

```text
source amount + related_to_operation=true
        -> related component and related total

related component
+ documented=true
+ actually_incurred=true
+ methodology legal rule
        -> allowed component and allowable total
```

If a related component lacks one allowability prerequisite, it remains in the
related total but receives `not_allowed_unproven` and is excluded from the
allowable total. There is no fallback from related to allowable.

## Declaration adapter

The Tax Model shape is independent of the G5.12 synthetic proof-input shape.
A private mechanical adapter projects only these stable meanings:

```text
operation category
category gross income
related expense total
allowable expense total
loss treatment
```

The adapter performs no tax arithmetic, category choice, declaration-code
choice, or missing-value repair. It contains no XML path, attribute, or code.
G5.12 remains the sole declaration representation owner.

## Fail-closed boundary

- missing or unsupported operation, market, IIS, period, residency, or
  exemption prerequisite blocks category production;
- missing explicit loss treatment never becomes `none`;
- incomplete scope blocks category gross-income completeness;
- unsatisfied G5.5 requirements block the model;
- multiple matching source values are rejected by G5.4/G5.5 or the scalar
  money resolver;
- mixed currencies are rejected before totals;
- related but unproven expense is excluded from allowable total;
- invalid methodology shape/evidence binding, unknown behavior, resource
  identity mismatch, or resource hash mismatch fails closed;
- no partial Tax Model or declaration fragment is persisted.
- a missing exact-target transaction charge on the G5.40D path blocks Tax
  Model production; it never becomes zero.

## Representative result

The closed proof obtains:

```text
Financial Case gross income       100.00 RUB
Supplemental acquisition cost      70.00 RUB
Supplemental transaction expense    2.00 RUB

related expense total              72.00 RUB
allowable expense total            72.00 RUB
loss treatment                     none
stable category                    organized_market_securities_outside_iis
```

The G5.12 projector then produces the same five-attribute Appendix 8 fragment
as G5.12. The `100 - 72` difference is intentionally not calculated or named
by this slice.

## KISS and stop condition

G5.13 adds one small Tax Model module, one hash-pinned methodology resource,
one closed input/model/result contract, one semantic adapter, and focused
tests. It adds no Tax Case, repository, DB/table, annual aggregator, Tax
Context framework, rules DSL, reference platform, workflow, LLM, full
declaration serializer, tax rate, or tax calculation.

The representative semantic and projection proof passed with explicit
production-evidence gaps, so `G5.13_CLOSED`. At that closure this contract did
not itself authorize a later Gate 5 slice.

The additive G5.14 compatibility seam adds one new hash-pinned methodology
version and one operation-only result shape inside the same owner. Category
scope, completeness binding and aggregation remain owned by the separate
G5.14 contract.

The additive G5.40D seam adds no second Tax Model or source reader. Its bounded
FIFO, source-granularity and unresolved-methodology rules are owned by
[Deterministic Source-Fact Consumption v0](./BROKER_REPORTS_GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION.v0.md).

The Issue #293 seam adds composition only. The existing operation behavior,
methodology hashes, Fact v2 validator and category owner remain the sole
authorities for their meanings.
