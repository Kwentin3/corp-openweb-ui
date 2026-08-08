# Broker Reports Pipeline Gates v1

Status: `CURRENT`

Classification: `CURRENT AUTHORITY`

Date: 2026-08-06

Updated: 2026-08-08

```text
CURRENT_PIPELINE_AUTHORITY = ONE
CanonicalArtifactV1 = OUTPUT OF GATE 2
GATE3_STATUS = CLOSED
GATE4_STATUS = NEXT / NOT_YET_DESIGNED_HERE
```

This contract is the sole current authority for Broker Reports gate numbering,
data ownership and gate-to-gate outputs. Versioned contracts own the exact DTO
shapes; the architecture-authorities map owns maintained factories. Dated
reports prove a bounded revision but cannot redefine this pipeline.

## Current sequence

| Gate | Input | Owned responsibility | Authoritative output | Status |
| --- | --- | --- | --- | --- |
| Gate 1 | authenticated source | custody, access checks, format detection, original-byte storage and route selection | stored source identity and intake/routing receipt | current |
| Gate 2 | exact Gate 1 source identity plus trusted `ArtifactAccessContext` | format-specific extraction, deterministic non-financial normalization, validation and immutable version storage | validated immutable `CanonicalArtifactV1` | current |
| Gate 3 | exact active validated `CanonicalArtifactV1`, read through `CanonicalReaderFactory.create` | financial semantic labeling plus source-bound role labeling: sparse selection of known types, then role bindings for the selected facts | immutable `FinancialAnnotationsV2` sidecar bound to that exact canonical version | `CLOSED`; active only in the NDFL workflow |
| Gate 4 | not defined here | separate downstream stage | not defined here | `NEXT / NOT_YET_DESIGNED_HERE` |

## Gate 3 meaning

Gate 3 reads one canonical document version, may divide its projection into
bounded structural chunks, attaches only published financial labels, then
binds each selected fact to the roles allowed by the published Role Pack. A
binding contains a canonical target and, only when the target contains larger
text, an optional exact literal `exact_text`. Missing roles are explicit and
are never guessed. The result is one separate annotation layer.

Gate 3 does not:

- mutate `CanonicalArtifactV1`;
- parse original PDF, HTML, CSV or XLSX bytes;
- combine different documents into one labeling context;
- calculate tax, cost basis or FIFO;
- reconcile a tax case or build a declaration;
- perform or define Gate 4.

Sparse omission, including `annotations: []`, makes no absence or completeness
claim.

After establishing the matching canonical version, downstream deterministic
code may resolve a bound role through `Gate3RoleValueResolverFactory.create`;
the product path uses `create_from_active_canonical` with the sidecar's expected
version. Neither route needs to understand broker column names or ask an LLM
which source value is a date, asset, quantity, price, amount or currency. A
required role with `status=missing` remains explicitly unavailable.

## Identity and version invariants

The product handoff is persisted identity, not copied text:

```text
Gate 1 source identity
-> validated CanonicalArtifactV1 version A
-> FinancialAnnotationsV2 for version A
```

`FinancialAnnotationsV2` is bound to the exact canonical version, root and
payload identity used for labeling.

```text
Canonical version A -> Annotations A
Canonical version B != Annotations A
```

Activating version B makes annotations for version A stale for current-version
downstream use. Version B requires its own Gate 3 result.

## Current product boundary

The only user-facing Gate 3 product route is Workspace Model/workflow stable ID
`broker-reports-ndfl`. It reuses technical base Pipe
`broker_reports_gate1_pipe`; that Pipe is internal runtime infrastructure, not
a second user product. Behavioral routing uses stable IDs, never display names.

`gate2_handoff_v0` remains a compatibility read authority for consumers not
explicitly migrated. It is not the NDFL Gate 2 -> Gate 3 handoff and is not a
second current pipeline output. The NDFL route resolves an exact canonical
manifest reference through the canonical reader.
The global product canonical
read valve remains disabled outside explicitly authorized consumers.

## Current Gate 3 contract status

| Surface | Status |
| --- | --- |
| [Gate 3 Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) | `CURRENT_ACTIVE_IN_NDFL` |
| current Gate 3 projection | `ACTIVE_IN_NDFL` |
| [current Gate 3 financial-label dictionary](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md) | `ACTIVE_IN_NDFL` |
| current Gate 3 bounded labeling | `ACTIVE_IN_NDFL` |
| [current Gate 3 Role Pack and role labeling](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) | `ACTIVE_IN_NDFL` |
| current Gate 3 FinancialAnnotations persistence | `ACTIVE_IN_NDFL` |
| NDFL exact-identity product route | `G3.C5_ACTIVE` |
| terminal Gate 3 system result | `G3.C5_CLOSED` |

## Authority and non-authority

- `CanonicalArtifactV1` and its schema own Gate 2 normalized document meaning.
- `CanonicalReaderFactory.create` is the sole canonical read boundary.
- `FinancialAnnotationsV2` and its schema own the current Gate 3 sidecar
  shape. V1 remains the immutable historical label-only contract.
- `broker-reports-financial-labels@<version>` is the sole financial-label
  meaning owner.
- `broker-reports-financial-roles@<version>` is the sole role/profile and
  source-binding-rule owner.
- Provider output is a proposal; validation and persistence do not make the
  provider an authority.
- Original source bytes, parser units, crops, private evidence and provider
  payloads remain outside the Gate 3 input contract.
- Native OpenWebUI document processing, Knowledge/RAG, embeddings and
  vectorization are outside this pipeline.

## Documentation precedence

1. This contract owns the current Gate 1-4 map and gate status.
2. Versioned DTO contracts own payload meaning and invariants.
3. `BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md` owns maintained implementation
   entrypoints and duplicate-prevention boundaries.
4. `BROKER_REPORTS_GATE3_HANDOFF.v1.md` is the short current supporting handoff.
5. Dated reports and receipts are evidence only.
6. Research, proposals, drafts and superseded blueprints are not current
   authority.

The older `BROKER_REPORTS_GATE_ARCHITECTURE.md` and its derived pre-Gate-3
maps are `SUPERSEDED` for current gate meaning. They remain readable as
historical migration context and cannot override this contract.
