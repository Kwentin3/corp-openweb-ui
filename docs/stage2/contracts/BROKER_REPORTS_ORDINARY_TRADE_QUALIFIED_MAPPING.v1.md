# Ordinary Trade Qualified Mapping Contract v1

Status: `CURRENT AUTHORITY`

Updated: 2026-08-27

## Definition

A qualified semantic mapping is an immutable set of source-schema decisions
needed by a named downstream consumer. Runtime may execute it; runtime may not
invent, extend or repair it.

The executable mapping and its qualification receipt are separate obligations:

- mapping v3 says what exact headers, roles, literal enums and
  `amount_column -> currency_column` pairs to execute;
- qualification receipt v2 distinguishes direct source wording from a reviewed
  source-schema interpretation, pins the exact fingerprint and semantic scope,
  and names the consuming Fact v2 contract.

Production admission requires both objects and exact identity/hash agreement.
A structurally valid mapping without its matching receipt is only a candidate,
not production authority.

The frozen receipt-v2 registry is the zero-model-call fast path, not an
admission list. An unknown exact schema follows the separate
[Automatic Semantic Mapping v1](./BROKER_REPORTS_ORDINARY_TRADE_AUTOMATIC_SEMANTIC_MAPPING.v1.md)
case flow. Only an explicitly confirmed, exact-context case receipt v1 may be
executed, and it is never promoted to or reused as a global registry entry.

## Admission law

A source-schema relation may be admitted only when all are true:

1. a current consumer needs the distinction;
2. the relation is supported by exact source-schema wording or by a frozen,
   explicit review of that schema scope;
3. the evidence surface is part of the exact structural fingerprint;
4. the receipt covers every executable relation with no missing or extra pair;
5. the mapping and receipt pass the package-owned authority validator.

A successful test, expected Gate 5 result, column proximity, repeated row
values, another table, reconciliation or broker identity is not evidence of
source meaning.

## Epistemic meaning

The receipt is an authorization and audit record. It does not turn a reviewed
interpretation into direct source wording and must not be described as doing
so.

`EXPLICIT_DENOMINATION_HEADER` means the exact admitted amount header itself
names its denomination. `REVIEWED_SCHEMA_SCOPE` means the relation is not
directly worded and is admitted only after review of the exact title plus the
complete ordered header set. Every such claim contains a unique review record
with the precise question, decision, rationale and the evidence classes that
were explicitly excluded. The receipt hash seals that record together with the
relation and exact evidence surface.

The receipt's historical model `supporting_decisions` are explicitly scoped to
column-role and side-enum decisions. They are not evidence for any
`amount -> currency` relation.

The historical `QUALIFIED_SCHEMA_SCOPE` marker is insufficient for new or
current admission: it recorded that a decision existed but not what was
reviewed or why the decision was accepted. Qualification receipt v2 rejects it.

This distinction lets a later reviewer independently read the same source
surface and challenge the rationale. A receipt proves that this exact reviewed
decision was frozen and admitted; only an explicit header claim is direct
source-text proof.

`unit_price -> currency` is deliberately absent: no current consumer requires
that relation. A future consumer requires a new versioned claim and receipt;
it must not silently widen the present mapping.

## Frozen fast-path extension rule

For a new exact schema:

1. preserve the Canonical unchanged;
2. record the exact source surface and structural fingerprint;
3. add data-only column roles, literal enums and only consumer-required
   source-schema relations;
4. add a matching qualification receipt;
5. prove wrong binding, stale receipt and unknown schema fail closed;
6. run the current ordinary-route tests and exact-head CI.

STOP and retain `RELEVANT_UNMAPPED` when meaning depends on row values,
proximity, reconciliation, broker/year/filename, or schema-specific compiler
branches. A third or hundredth schema may add registry data; it must not add a
new runtime algorithm or broker profile.

## Ownership

- Canonical owns literal structure and provenance, not financial meaning.
- `OrdinaryTradeQualifiedMappingAuthorityFactory.create` owns production
  mapping admission and matching receipts.
- `OrdinaryTradeSemanticCompilerFactory.create` executes admitted mappings and
  deterministic syntax transforms only.
- Gate 4 consumes the projection through its existing Fact v2 boundary.
- Gate 5 consumes Fact v2 and never reads Canonical or qualification receipts.
- Historical Gate 3 is deployment rollback compatibility, not a fallback.
