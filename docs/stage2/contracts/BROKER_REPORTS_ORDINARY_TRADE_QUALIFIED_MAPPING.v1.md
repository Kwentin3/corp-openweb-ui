# Ordinary Trade Qualified Mapping Contract v1

Status: `CURRENT AUTHORITY`

Updated: 2026-08-22

## Definition

A qualified semantic mapping is an immutable set of source-schema decisions
needed by a named downstream consumer. Runtime may execute it; runtime may not
invent, extend or repair it.

The executable mapping and its qualification receipt are separate obligations:

- mapping v3 says what exact headers, roles, literal enums and
  `amount_column -> currency_column` pairs to execute;
- qualification receipt v1 says why those pairs were admitted, pins the exact
  fingerprint and semantic scope, and names the consuming Fact v2 contract.

Production admission requires both objects and exact identity/hash agreement.
A structurally valid mapping without its matching receipt is only a candidate,
not production authority.

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

`unit_price -> currency` is deliberately absent: no current consumer requires
that relation. A future consumer requires a new versioned claim and receipt;
it must not silently widen the present mapping.

## Cold-start extension rule

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
