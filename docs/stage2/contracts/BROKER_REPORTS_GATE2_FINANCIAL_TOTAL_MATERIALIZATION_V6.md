# Broker Reports Gate 2 Financial Total Materialization V6

Status: Goal 7 contract for Candidate Records By Construction.

## Boundary

`Gate2FinancialSemanticV6TotalMaterializerFactory.create` is the only V6
entrypoint from an exact validated expansion to a canonical financial inputs
artifact. It revalidates the full expansion authority and delegates to the
existing `Gate2FinancialEvidenceMaterializerFactory`.

There is no second materializer and no provider-controlled execution metadata.

## Totality claim

For every decision that:

1. conforms to the minimal Choice Contract;
2. references the exact packet and Candidate Compilation;
3. passes deterministic expansion;
4. passes canonical decision validation;

the canonical materializer must return one valid terminal artifact with the
same disposition.

The forbidden state `canonical validation passed / materialization failed` is
reported as `financial_semantic_v6_validated_but_unmaterializable` and has zero
accepted instances.

## Structural proof

Typed Options are admitted upstream only after a real canonical materializer
proof. At final materialization the boundary independently checks:

- exact role cardinality and required roles;
- date/period and currency/unit completeness;
- source-sign policy;
- identity roles;
- exact Pack and Registry identity;
- exact source-package and scope ownership;
- terminal source-value parity;
- canonical artifact integrity and validation.

Unclassified materialization must contain every Bundle retention ref exactly
once and must never publish a typed input.

## No repair

The boundary cannot change the disposition, bindings, retained refs, type, or
reason. Any authority mismatch or materializer exception fails closed. There
is no fallback, retry, or post-response repair.
