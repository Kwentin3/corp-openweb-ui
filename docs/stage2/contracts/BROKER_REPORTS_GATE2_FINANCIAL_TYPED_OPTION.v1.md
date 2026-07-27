# Broker Reports Gate 2 Financial Typed Option v1

Status: authoritative V6 precomputed-record boundary contract

Schema identity:
`broker_reports_gate2_financial_typed_option_v1`

## Purpose

A Typed Option is a complete, immutable record proposal prepared by code
before the semantic model call. The model may select its opaque
`typed_option_id`; it cannot create or modify the type, roles, source refs,
provenance, retention or record fields.

## Construction authority

`Gate2FinancialTypedOptionFactory.create()` is the only construction
entrypoint.

It accepts:

- one validated V6 Evidence Bundle;
- the exact sealed source package linked by that bundle;
- the exact Financial Semantic Pack/Registry snapshot;
- one exact `input_type_id`;
- a complete code-owned role map containing every required and optional role.

The factory makes no model or provider call.

## Structural requirements

An option is created only when:

- the type exists exactly in the frozen Financial Semantic Pack;
- the source family is compatible with that type;
- the supplied role set equals the type's required and optional role set;
- every required role is bound;
- every optional role is explicitly bound or `null`;
- each role's technical value type matches the Pack role contract;
- every bound source ref belongs to the Evidence Bundle;
- no source ref is reused for two roles;
- all identity roles are present;
- all bound values share one authoritative source association;
- date/period and currency/unit requirements are satisfied;
- current role cardinalities are exactly representable as `one` or
  `zero_or_one`.

The factory does not inspect literals, labels or financial words and contains
no concrete type-specific branch.

## Materializability requirement

Before returning an option, the factory:

1. constructs a generic canonical decision adapter from Pack role value
   types;
2. submits the code-owned typed decision through the existing canonical
   decision validator;
3. runs the existing universal materializer with deterministic proof
   metadata;
4. requires one typed input, zero unclassified inputs and a valid terminal
   artifact.

Any validator or materializer failure rejects option construction. The
resulting materializability receipt pins:

- canonical decision schema hash;
- Semantic Pack and Registry identity;
- source-package integrity;
- materialization schema and policy;
- exact artifact and typed-input integrity hashes.

## Option fields

The option contains:

- an opaque, content-derived `typed_option_id`;
- Evidence Bundle identity and integrity;
- exact `input_type_id`;
- required and optional role lists;
- prebound role-to-source-ref bindings;
- a structural compatibility receipt;
- a materializability receipt;
- an option integrity hash.

## Privacy

The private option contains source refs but no source literals.

`safe_summary()` contains the opaque option ID, public type ID, counts,
receipt hashes and boolean invariants. It contains no source literal,
source-value ref, provenance ref or raw provider output.

## Acceptance

- `TYPED_OPTION: FULLY_MATERIALIZABLE`
- `MODEL_GENERATED_REFS: ZERO`
- `MODEL_GENERATED_ROLES: ZERO`
- `REQUIRED_ROLE_GAPS: ZERO`
