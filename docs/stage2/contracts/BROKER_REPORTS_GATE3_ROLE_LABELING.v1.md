# Broker Reports Gate 3 Role Labeling v1

Status: `CURRENT_ACTIVE_IN_NDFL`

Date: 2026-08-08

## Purpose

This contract closes document understanding inside Gate 3 for facts already
selected by the sparse financial-type pass. It does not claim that every
financial fact in a document was found.

```text
same Gate3 structural chunk
+ validated pass-1 facts and labels
+ broker-reports-financial-roles@1.0.0
-> one role proposal for all facts in that chunk
-> fail-closed backend validation and alias restoration
-> FinancialAnnotationsV2
```

If pass 1 returns no annotations for a chunk, pass 2 is skipped. Otherwise
there is exactly one pass-2 provider call for the chunk, never one call per
fact. Both passes reuse the existing projection, chunk boundaries, aliases,
provider client and adapter route. There is no retrieval, RAG or dynamic
routing.

## Sole Role Pack authority

The hash-pinned package resource loaded only through
`Gate3FinancialRolePackFactory.create` owns:

- role definitions;
- financial label to required/optional role profiles;
- source-value and `exact_text` rules;
- maximum-one binding cardinality;
- the ban on normalized or computed values.

Its current identity is `broker-reports-financial-roles@1.0.0`. Python,
instructions, Skills and adapters may describe the response protocol but must
not copy these role/profile definitions.

The exact current role set and all nine profiles live only in the
[published Role Pack resource](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_role_pack.v1.json).
`related_fact` is not present in that source of truth.

## Pass-2 input and response

Backend code creates deterministic `fact_alias` values for the validated
pass-1 facts and shows each alias together with its unchanged
`financial_label` and original target alias. The model also receives the
complete Role Pack and the same chunk Markdown.

`Gate3RoleLabelingResponseV1` contains only:

```text
schema_version
facts[]:
  fact_alias
  financial_label
  roles[]:
    role
    status = bound | missing
    target_alias  # bound only
    exact_text    # optional, bound only
```

Every allowed role appears exactly once. A required role may be explicit
`missing`; this preserves uncertainty and makes the fact mechanically
detectable as role-incomplete. The model must not guess a value.

For `status=bound`, `target_alias` is an exact bare alias from the same chunk.
If the canonical target itself is the complete value, `exact_text` is absent.
If the value is inside larger target text, `exact_text` is the non-empty exact
case-sensitive literal substring. It is neither a normalized value nor a
computed value. A composite target with more than one source scalar cannot be
resolved without `exact_text`; the literal must occur inside one actual source
scalar and cannot span an artificial row serialization.

## Backend validation

`Gate3RoleLabelingFactory.create_from_chunk` rejects the complete proposal if:

1. a fact alias is missing, duplicated or unknown;
2. a response label differs from the validated pass-1 label;
3. a role is unknown or not allowed by the exact profile;
4. an allowed role is missing from the response or appears more than once;
5. a bound target alias is not in the exact chunk mapping;
6. the restored canonical target does not exist in the exact active version;
7. `exact_text` is empty, longer than the contract limit or is not a literal
   substring of that canonical target's text;
8. a composite target without `exact_text` would leave more than one possible
   source value;
9. a `missing` binding carries a target or copied value;
10. canonical, dictionary, Role Pack, instruction or model identities differ.

No stripping, fuzzy matching, response repair, retry or fallback is allowed.
Chunk merge preserves structural chunk order, fact order inside each pass-1
result and Role Pack order inside each fact.

`Gate3FinancialAnnotationsPersistenceFactory.create` repeats the current
canonical binding, target membership, profile/cardinality and literal
`exact_text` checks before immutable save.

## FinancialAnnotationsV2

V2 is the current version of the same logical Gate 3 sidecar, not a second
source of financial truth:

```text
schema_version = broker_reports_financial_annotations_v2
canonical_binding
dictionary_identity
role_pack_identity
instruction_identity
role_instruction_identity
model_identity
annotations[]:
  target
  financial_label
  roles[]:
    role
    status = bound | missing
    target      # bound only
    exact_text  # optional, bound only
validation_status = validated
```

V1 remains immutable historical label-only evidence and is still readable
through the same persistence owner. New current writes and current readiness
use V2 only. A sidecar for canonical version A is stale when version B becomes
active; version B requires its own type and role passes.

## Deterministic downstream boundary

`Gate3RoleValueResolverFactory.create(canonical_artifact=...)` resolves a
persisted binding without financial or broker-specific logic. Product
validation uses the same owner through `create_from_active_canonical`, which
delegates the exact active-version read to `CanonicalReaderFactory.create`:

```text
status=missing -> None
bound + exact_text -> exact_text after literal-substring verification
bound without exact_text -> the target's sole non-empty canonical source scalar
```

Therefore ordinary code can obtain the already-labeled fact type and its
applicable date, asset, quantity, unit price, amount and currency. It does not
need to decide what a broker column means. Parsing or normalizing those source
strings for a later SQL representation is downstream deterministic work.

## Preserved invariants and non-goals

- sparse pass-1 omission remains a non-claim;
- CanonicalArtifactV1 is immutable and read only through
  `CanonicalReaderFactory.create`;
- artifacts remain exact-version bound and immutable;
- dictionary, Role Pack, instruction and model identities are persisted;
- raw provider payload remains private and outside the sidecar;
- validation fails closed.

This contract does not design SQL or Gate 4, perform cross-document linking,
relations, FIFO, cost basis, tax calculations, reconciliation, broker-specific
adapters, a relation ontology, RAG, a database or new orchestration.

## Direct schemas

- [Role Pack v1 schema](./BROKER_REPORTS_GATE3_FINANCIAL_ROLE_PACK.v1.schema.json)
- [Role response v1 schema](./BROKER_REPORTS_GATE3_ROLE_LABELING_RESPONSE.v1.schema.json)
- [FinancialAnnotationsV2 schema](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json)
- [shared canonical target v1](./BROKER_REPORTS_GATE3_TARGET.v1.schema.json)
