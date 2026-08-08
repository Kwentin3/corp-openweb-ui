# Broker Reports Pipeline Gates v1

Status: `CURRENT`

Classification: `CURRENT AUTHORITY`

Date: 2026-08-06

Updated: 2026-08-08

```text
CURRENT_PIPELINE_AUTHORITY = ONE
CanonicalArtifactV1 = OUTPUT OF GATE 2
GATE3_STATUS = CLOSED
GATE4_STATUS = G4.3 MULTI-DOCUMENT FINANCIAL CASE ASSEMBLY CLOSED
G4.4_RESEARCH_STATUS = CLOSED — NO_RELATION_LAYER_NEEDED_YET
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
| Gate 4 | current validated `FinancialAnnotationsV2` sidecars plus their exact active canonical bindings and trusted `ArtifactAccessContext` | materialize immutable typed facts and assemble every current eligible document into one technically scoped case set; later relation/read capabilities remain separately approved | current `Gate4FinancialCaseFactV1` set plus non-authoritative working SQL cache and derived case completeness | `G4.3_CLOSED`; `G4.4_RESEARCH_CLOSED`; G4.5 not applicable without new evidence; G4.6-G4.7 not started |

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
- perform Gate 4 materialization, case assembly, relations or reads.

Sparse omission, including `annotations: []`, makes no absence or completeness
claim.

After establishing the matching canonical version, downstream deterministic
code may resolve a bound role through `Gate3RoleValueResolverFactory.create`;
the product path uses `create_from_active_canonical` with the sidecar's expected
version. Neither route needs to understand broker column names or ask an LLM
which source value is a date, asset, quantity, price, amount or currency. A
required role with `status=missing` remains explicitly unavailable.

## Current Gate 4 boundary

[Gate 4 Financial Case Fact v1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md)
defines the smallest current Gate 4 semantic unit. It binds one typed financial
fact to the existing server-attested case/chat scope, one exact immutable
`FinancialAnnotationsV2` artifact and annotation index, the matching canonical
version, source-backed role literals and explicit missing roles.

G4.1 remains the sole fact-shape authority. G4.2 implements ordinary-code
materialization through the existing Gate 3 role resolver and a minimal SQL
projection in the existing ArtifactStore SQLite file. Exact cache generation
bindings fail closed when the selected sidecar or active canonical changes;
ArtifactStore lifecycle removes derived rows. The cache is deletable and
rebuildable and owns no financial meaning. G4.3 uses the existing readiness
owner to derive every current case document, invokes
the G4.2 materializer per exact eligible sidecar and atomically replaces the
same two cache tables. Its `CASE_COMPLETE_FOR_CURRENT_INPUT_SET` status is only
technical assembly completeness; it is not economic, tax or corpus
completeness. Similar-looking facts remain separate. Relations,
reconciliation, tax logic, API and user-facing product activation remain
absent. The historical Managed Financial Domain remains compatibility code,
not current Gate 4.

G4.4 research found no current downstream task that requires a separately
persisted semantic relation. Queryable proximity by type, asset, date, amount
or source remains a query, not an assertion that two facts are the same,
related or conflicting. Therefore the current minimal relation set is empty,
G4.5 has no implementation subject without new evidence, and G4.6 is the next
allowed Goal. The closure-era next-Goal pointers in G4.1 and G4.3 describe the
sequence before this decision; this sole pipeline authority owns the current
sequence.

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
G4.2/G4.3 are packaged as one internal factory/runtime slice in the same
OpenWebUI Function bundle. They add no new user action, API or second product
route.

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

## Current Gate 4 contract status

| Surface | Status |
| --- | --- |
| [Gate 4 Financial Case Fact v1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md) | `G4.1_CLOSED` |
| [Gate 4 deterministic materializer and SQL cache](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md) | `G4.2_CLOSED` |
| [Gate 4 multi-document case assembly](./BROKER_REPORTS_GATE4_CASE_ASSEMBLY.v1.md) | `G4.3_CLOSED` |
| [G4.4 relation-necessity research](../../reports/2026-08-08/BROKER_REPORTS_GATE4_RELATION_NECESSITY_G4_4.report.md) | `G4.4_RESEARCH_CLOSED — NO_RELATION_LAYER_NEEDED_YET` |
| G4.5 relation implementation | `NOT_APPLICABLE_WITHOUT_NEW_EVIDENCE` |
| G4.6 read boundary | `NOT_STARTED — NEXT_ALLOWED_GOAL` |
| representative Gate 4 closure | `G4.7_NOT_STARTED` |

## Authority and non-authority

- `CanonicalArtifactV1` and its schema own Gate 2 normalized document meaning.
- `CanonicalReaderFactory.create` is the sole canonical read boundary.
- `FinancialAnnotationsV2` and its schema own the current Gate 3 sidecar
  shape. V1 remains the immutable historical label-only contract.
- `broker-reports-financial-labels@<version>` is the sole financial-label
  meaning owner.
- `broker-reports-financial-roles@<version>` is the sole role/profile and
  source-binding-rule owner.
- `Gate4FinancialCaseFactV1` and its schema own only the current minimal Gate 4
  fact shape; they do not own financial type/role meaning or storage.
- `Gate4FinancialCaseMaterializerFactory.create` owns only the deterministic
  V2-to-fact projection; `Gate4FinancialCaseRuntimeFactory.create` owns rebuild
  and explicit reads over the non-authoritative cache.
- `Gate4FinancialCaseRuntimeFactory.create` also owns only deterministic G4.3
  case assembly over the Gate 3 readiness source set; it does not own
  duplicate, relation, reconciliation or completeness-of-financial-history
  meaning.
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
4. `BROKER_REPORTS_GATE3_HANDOFF.v1.md` is the short current supporting handoff
   into the G4.1 fact and G4.2/G4.3 runtime contracts.
5. Dated reports and receipts are evidence only.
6. Research, proposals, drafts and superseded blueprints are not current
   authority.

The older `BROKER_REPORTS_GATE_ARCHITECTURE.md` and its derived pre-Gate-3
maps are `SUPERSEDED` for current gate meaning. They remain readable as
historical migration context and cannot override this contract.
