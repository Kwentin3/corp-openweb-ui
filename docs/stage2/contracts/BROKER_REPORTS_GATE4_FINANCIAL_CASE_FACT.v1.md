# Broker Reports Gate 4 Financial Case Fact v1

Status: `CURRENT_CONTRACT`

Goal status: `G4.1_CLOSED`

Runtime status: `IMPLEMENTED_BY_G4.2`

Gate 4 status: `CLOSED_BY_G4.7`

Date: 2026-08-08

## Purpose

This contract defines the smallest current Gate 4 semantic unit: one financial
fact inside one server-attested case or chat scope.

```text
current validated FinancialAnnotationsV2 artifact
+ exact active CanonicalArtifactV1
+ existing ArtifactAccessContext
-> deterministic Gate4FinancialCaseFactV1
```

G4.1 defines the logical output and its invariants only; it did not add a
runtime, storage write, SQL table, relation or product route. G4.2 now owns the
deterministic materializer and rebuildable SQL projection documented in
[Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md).

The normative machine-readable shape is
[Gate4FinancialCaseFactV1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.schema.json).

## Ownership

| Concern | Current owner | Gate 4 rule |
| --- | --- | --- |
| document structure and provenance | exact `CanonicalArtifactV1` read through `CanonicalReaderFactory.create` | read only; never reinterpret source formats |
| financial type | current Gate 3 financial dictionary and validated annotation | copy the exact selected label as `financial_type` |
| applicable roles and required/optional meaning | exact Gate 3 Role Pack identity pinned by the sidecar | derive; do not copy profiles into Gate 4 code or schema |
| source value resolution | `Gate3RoleValueResolverFactory.create_from_active_canonical` | reuse; do not add broker or column rules |
| user/case/chat/workspace authority | OpenWebUI-injected context represented by `ArtifactAccessContext` | derive case binding from trusted context; never accept caller scope as authority |
| access, retention and purge | existing ArtifactStore/ArtifactResolver lifecycle | remain outside the fact payload and are not reimplemented |
| one current Gate 4 fact shape | this contract and schema | one versioned boundary; no parallel record catalog |

The historical Managed Financial Domain remains compatibility evidence. It is
bound to the superseded Gate 2 classification, terminal-coverage, registry,
HMAC snapshot and query model. Activating or adapting that entire subsystem
would import responsibilities that the current Gate 4 does not need. It is not
a second current Gate 4 authority.

## One fact

`Gate4FinancialCaseFactV1` contains exactly:

```text
schema_version
fact_id
case_binding
gate3_binding
financial_type
annotation_target
roles[]
status = role_complete | role_incomplete
```

No case aggregate is introduced by G4.1. A Financial Case is the set of
current Gate 4 facts carrying the same trusted `case_binding`. Multi-document
assembly is now implemented by
[Gate 4 Case Assembly v1](./BROKER_REPORTS_GATE4_CASE_ASSEMBLY.v1.md);
G4.4 found no current need for semantic relations, so the minimal relation set
is empty and G4.5 is `NOT_APPLICABLE_WITHOUT_NEW_EVIDENCE`.

Sparse Gate 3 omission remains a non-claim. If a current sidecar contains zero
annotations, it produces zero Gate 4 facts and no assertion that the document
has no financial activity.

## Fact identity

`fact_id` is reproducible for one exact upstream annotation. G4.2 must compute
it as:

```text
g4fact_ + first 32 lowercase hex characters of SHA-256(
  canonical UTF-8 JSON of {
    schema_version,
    case_binding,
    financial_annotations_artifact_id,
    annotation_index,
    canonical_binding,
    financial_type
  }
)
```

Canonical JSON has lexicographically sorted object keys, no insignificant
whitespace, preserved Unicode and no non-finite numbers. The `annotation_index`
is zero-based in the exact immutable `FinancialAnnotationsV2.annotations`
array.

The same case scope, sidecar and annotation therefore rebuild the same ID. A
new sidecar, canonical version, annotation position or financial type produces
a different ID. Gate 4 never mutates an existing fact into a new upstream
meaning.

## OpenWebUI-first case binding

Gate 4 does not mint a parallel case registry.

`case_binding` is derived from the existing server-injected
`ArtifactAccessContext`:

- use `scope_kind=case` and the exact `case_id` when present;
- otherwise use `scope_kind=chat` and the exact `chat_id`;
- reject when neither trusted scope exists.

User identity, workspace identity, permissions, retention timestamps and purge
state remain in the existing ArtifactStore envelope. They are not copied into
the semantic payload. A future stored fact must match its enclosing trusted
artifact scope exactly.

Native OpenWebUI File remains source-upload custody. Native Chat and Knowledge
are not private financial-data stores, and Knowledge/RAG/vectorization remain
outside this pipeline. G4.1 changes no OpenWebUI upstream model, API or table.

## Exact Gate 3 binding

`gate3_binding` contains:

- the immutable `FinancialAnnotationsV2` ArtifactStore ID;
- the exact current V2 schema identity;
- the zero-based annotation index;
- the annotation's exact `document_id` and `canonical_version_id`.

The referenced artifact must be readable through the existing
ArtifactResolver under the same trusted context, must validate as current V2,
and must match the exact active canonical version. G4.2 must fail before
materialization when any of those checks fail.

`annotation_target` is copied unchanged from that exact annotation and reuses
the shared Gate 3 target schema. Gate 4 does not create another locator grammar.

## Typed role values

Only roles applicable to the exact financial type's Role Pack profile appear.
Each applicable role appears once, in the existing profile order, with its
derived `requirement=required|optional` and one of two states:

```text
status=value
value=<normalized typed string>
source_binding:
  target=<exact Gate 3 role target>
  exact_text=<exact optional Gate 3 literal>
  source_literal=<exact resolver result>

or

status=missing
```

Roles absent from the profile are not applicable and are omitted. They are not
silently converted to `missing`.

Role determines the value type:

| Role | Gate 4 value |
| --- | --- |
| `date` | valid ISO calendar date `YYYY-MM-DD` |
| `quantity`, `unit_price`, `amount` | canonical finite decimal string without exponent or grouping separators |
| `asset`, `currency` | non-empty string |

Decimal values remain strings so JSON and SQL adapters cannot introduce binary
floating-point changes. The exact `source_literal` is retained separately from
the normalized value. G4.2 implements the small fail-closed policy: exact
`YYYY-MM-DD` or `DD.MM.YYYY` dates; decimals without grouping or exponent and
with one optional dot/comma fractional separator; surrounding whitespace only
for asset/currency. This does not change the G4.1 fact meaning.

For a value role, `source_binding.target` and optional `exact_text` are exact
copies from Gate 3, and `source_literal` is the exact output of the existing
resolver. For a missing role there is no invented target, literal or value.

## Fact status

- `role_complete`: no required applicable role is `missing`;
- `role_incomplete`: at least one required applicable role is `missing`.

An optional missing role does not make the fact incomplete. Invalid or stale
input is not represented as another fact status; materialization fails closed.

Conflict and ambiguity between different facts are not fact statuses in G4.1.
G4.4 found no current consumer evidence that requires separate persisted
relation assertions.

## Provenance chain

The contract preserves this mechanical trace:

```text
case_binding
-> fact_id
-> financial_annotations_artifact_id + annotation_index
-> annotation_target / role source_binding
-> canonical_binding
-> CanonicalArtifactV1 provenance
-> original OpenWebUI source file identity
```

The Gate 4 fact does not copy source filenames, filesystem paths, provider
payloads or raw documents. A later read boundary may project this provenance
without exposing physical storage or the Gate 3 target grammar to Gate 5.

## Stale and rebuild semantics

Gate 4 materialization is allowed only from the current validated V2 sidecar
whose canonical binding equals the exact active canonical version. If version
A becomes B, facts bound to A are stale for the current case and must not be
silently retained as current or rebound to B. B requires its own current Gate
3 result and new Gate 4 facts.

The SQL cache is never authoritative. Deleting it must not delete upstream Gate
3 artifacts or future versioned Gate 4 semantic outputs. Rebuilding from the
same exact inputs and contract produces byte-equivalent facts and identical
fact IDs. Persistence and cache replacement mechanics are owned by
[Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md).

## Representative fit

The current Gate 3 role-complete proof maps without financial interpretation:

| Financial type | Typed Gate 4 roles |
| --- | --- |
| `SECURITY_PURCHASE` | date, asset, quantity, amount, currency, optional unit price |
| `SECURITY_DISPOSAL` | date, asset, quantity, amount, currency, optional unit price |
| `DIVIDEND_INCOME` | date, amount, currency, optional asset; literal `exact_text` remains source provenance |
| `TRANSACTION_CHARGE` | date, amount, currency; optional missing asset remains explicit |
| `TAX_WITHHELD` | date, amount, currency; optional missing asset remains explicit |

The contract does not claim that Gate 3 found every fact in a document.

## G4.1 non-goals

G4.1 does not add or authorize:

- a materializer, SQL table, ORM, migration or cache;
- an ArtifactStore artifact type or persistence write;
- multi-document case assembly or destructive deduplication;
- relations, reconciliation, conflict algorithms or LLM calls;
- broker-specific adapters or source-format reads;
- tax law, FIFO, cost basis, tax base, rate, deduction or declaration logic;
- REST/API, generic query language, RAG, embeddings, vector or graph database;
- changes to OpenWebUI upstream models, ACL, storage or lifecycle.

## Stop condition

G4.1 is closed when the schema and executable contract tests prove that a
current Gate 3 role-complete fact can be represented with deterministic
identity, typed values, explicit missing state and full upstream provenance,
while stale binding and storage/runtime work remain outside this Goal.

G4.2 implements this contract without changing its shape, G4.3 assembles its
unchanged facts across current case documents, and G4.6 exposes them through
the existing runtime. G4.7 closed Gate 4 without a relation layer or schema
change. Next allowed boundary: `GATE5_DESIGN` through
[Gate 4 -> Gate 5 Handoff v1](./BROKER_REPORTS_GATE4_HANDOFF.v1.md).
