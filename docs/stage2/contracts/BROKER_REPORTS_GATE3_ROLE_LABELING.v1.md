# Broker Reports Gate 3 Role Labeling v1

Status: `CURRENT_ACTIVE_IN_NDFL`

Date: 2026-08-08

Updated: 2026-08-17 (`G5.84` exact fact-alias duplicate localization)

## Purpose

This contract closes document understanding inside Gate 3 for facts already
selected by the sparse financial-type pass. It does not claim that every
financial fact in a document was found.

```text
validated pass-1 accepted canonical row/region target
+ validated pass-1 facts and labels
+ broker-reports-financial-roles@3.0.0
-> deterministic accepted-target role context
-> one role proposal for all facts in that chunk
-> fail-closed backend validation and alias restoration
-> FinancialAnnotationsV2
```

If pass 1 returns no annotations for a chunk, pass 2 is skipped. Otherwise
there is exactly one pass-2 semantic task for the chunk, never one task per
fact. That task permits at most one operational resubmission of the exact same
sealed request after a provider-unavailable outcome with no semantic response.
Both passes reuse the existing projection, chunk boundaries, aliases,
provider client and adapter route. Pass 2 does not receive unrelated targets
from that chunk. There is no retrieval, RAG or dynamic routing.

## Deterministic accepted-target role context

`Gate3RoleContextFactory.create_from_accepted_facts` is the sole context
builder. It runs only after pass 1 has been validated and emits
`broker_reports_gate3_role_context_v1`. Its inputs are the exact current chunk
and its accepted pass-1 facts; it does not read a broker format, provider
payload, historical case or financial template.

For each fact the context is closed as follows:

- a canonical node or list-item target retains only that exact accepted
  region;
- a canonical table-row or table-cell target retains the exact row plus cell
  aliases from the same canonical table row;
- the generated table header/title for that same table may be copied only as
  context-only text with target aliases removed;
- source row `1` from that same table may also be copied as context-only text
  with target aliases removed when it is outside the accepted fact row. This
  preserves source-visible column labels for projections that intentionally
  make no semantic-header claim; it does not classify row `1` as a header and
  does not make any of its targets selectable;
- unrelated chunk targets are excluded;
- canonical text rendered with `<br>` line separators is restored to line
  structure for readability; source literals are not normalized or computed.

The context records the current canonical binding, source chunk ID, accepted
target aliases, `allowed_role_target_aliases` for every fact, selected target
mappings, a deterministic context ID/hash and aggregate size/count metrics.
A private, hash-only role-provenance receipt records every validated role
literal's exact canonical target and its relation to the accepted annotation.
For an accepted canonical table row it records the exact node/row identity;
for a coarser node it explicitly reports `accepted_canonical_region_only`.

A same-page visual table projection is not an accepted-row binding. Gate 3
must not expand a coarse PDF page node into every projected table/row and ask
the role model to choose a row again. Such a projection may be current and
validated evidence, but without a deterministic projection-row to accepted
canonical-target identity it remains outside role context. Closing that gap
requires an upstream document/canonical boundary that exposes an exact row or
region target to semantic labeling; it cannot be repaired by downstream
broker vocabulary or page matching.

## Sole Role Pack authority

The hash-pinned package resource loaded only through
`Gate3FinancialRolePackFactory.create` owns:

- role definitions;
- financial label to required/optional role profiles;
- source-value and `exact_text` rules;
- maximum-one binding cardinality;
- the ban on normalized or computed values.

Its current identity is `broker-reports-financial-roles@3.0.0`. Versions 1.0.0
and 2.0.0 remain explicitly loadable historical evidence. Version 3.0.0
qualifies `asset` as a source-authored code or other unambiguous identifier;
when both a name and identifier are present, the identifier is the binding.
Python,
instructions, Skills and adapters may describe the response protocol but must
not copy these role/profile definitions.

The exact current role set and all twelve profiles live only in the
[published Role Pack resource](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_role_pack.v3.json).
`related_fact` is not present in that source of truth.

## Pass-2 input and response

Backend code creates deterministic `fact_alias` values for the validated
pass-1 facts and shows each alias together with its unchanged
`financial_label`, original target alias and exact per-fact
`allowed_role_target_aliases`. The model also receives the complete Role Pack
and only the deterministic accepted-target context. Instruction identity
`broker-reports-source-bound-role-labeling@1.1.0` explicitly forbids repeating
document-wide event discovery.

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

For `status=bound`, `target_alias` is an exact bare alias from that fact's
allowed row/region closure.
If the canonical target itself is the complete value, `exact_text` is absent.
If the value is inside larger target text, `exact_text` is the non-empty exact
case-sensitive literal substring. It is neither a normalized value nor a
computed value. A composite target with more than one source scalar cannot be
resolved without `exact_text`; the literal must occur inside one actual source
scalar and cannot span an artificial row serialization.

## Backend validation

`Gate3RoleLabelingFactory.create_from_chunk` restores facts in validated
pass-1 order. Response ordering therefore carries no identity meaning. It
rejects the complete proposal for structural or identity errors if:

1. a fact alias is missing or unknown;
2. a response label differs from the validated pass-1 label;
3. a role is unknown or not allowed by the exact profile;
4. an allowed role is missing from the response or appears more than once;
5. a `missing` binding carries a target or copied value;
6. canonical, dictionary, Role Pack, instruction or model identities differ.

A source-binding rejection is local to the exact role binding when its fact
alias, label, role and cardinality are already structurally valid. An unknown
target alias, a target outside the accepted fact context, an empty or
non-literal `exact_text`, or an ambiguous composite target is projected as the
same role with `status=missing`. The rejected target and literal never enter the
annotation. A rejected required role makes that fact mechanically
role-incomplete; other roles, facts and chunks remain independently usable.
The attempt records only privacy-safe role rejection coordinates and error
codes. A missing restored canonical target remains a whole-proposal identity
failure rather than a local source-binding case.

A duplicated **known** fact alias is local to that exact pass-1 fact only when
the unique response alias set still equals the complete expected alias set.
Every occurrence of the duplicated response fact is discarded; none is
selected by label, position, text or values. The already validated pass-1 fact
identity is retained with every allowed role set to explicit `missing`, and a
privacy-safe `gate3_role_fact_alias_duplicated` rejection is recorded for each
role. All other facts are restored only by their exact unique alias. A missing
alias, unknown alias, or any unequal unique alias set remains a complete
proposal rejection. This is not fuzzy reconciliation and does not merge
provider responses.

No stripping, fuzzy matching, response repair, semantic-response retry or
fallback is allowed.
Chunk merge preserves structural chunk order, fact order inside each pass-1
result and Role Pack order inside each fact.

`Gate3FinancialAnnotationsPersistenceFactory.create` repeats the current
canonical binding, target membership, profile/cardinality and literal
`exact_text` checks before immutable save. A `FULL` result may use the ordinary
save operation. A `DEMAND_SCOPED` result is a delta and may enter only the
non-destructive recovery operation defined by
[Demand-Scoped Recovery v1](./BROKER_REPORTS_GATE3_DEMAND_SCOPED_RECOVERY.v1.md).

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

Each persisted V2 artifact is an immutable version of the current logical
document projection; readiness selects the latest validated artifact for the
active Canonical version. A recovery publication therefore persists a newly
merged full current view. It never exposes a narrow demand delta to Gate 4.
`validation_status=validated` means every retained claim passed its own
contract; it does not assert that every required role is present. Explicit
`missing` roles preserve incompleteness as data rather than converting it into
truth or suppressing an independent fact.

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
