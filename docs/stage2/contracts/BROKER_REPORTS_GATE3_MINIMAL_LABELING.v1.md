# Broker Reports Gate 3 Minimal Labeling v1

Status: `CURRENT_ACTIVE_IN_NDFL_G3_C5_CLOSED`

Implementation status: `G3.2_ACTIVE_IN_NDFL`

Dictionary implementation status: `G3.3M_ACTIVE_IN_NDFL`

Structural chunking implementation status: `G3.4B_ACTIVE_IN_NDFL`

Chunk batch status: `G3.4C_ACTIVE_IN_NDFL`

Strict alias output status: `G3.4D_ACTIVE_IN_NDFL`

Persistence implementation status: `G3.5_ACTIVE_IN_NDFL`

Case-readiness implementation status: `G3.6_COMPLETED_INACTIVE`

Terminal proof status: `G3.C5_CLOSED`

Managed dictionary GUI binding: `active`

NDFL product-path activation: `true`

NDFL Gate 2 to Gate 3 handoff: `G3.C5_ACTIVE`

Product cutover: `NDFL_ONLY`

Date: 2026-08-06

Updated: 2026-08-08

## 1. Purpose

This contract defines the shared projection, alias and sparse financial-type
pass of Gate 3 over one active validated `CanonicalArtifactV1` version. The
current role-complete continuation is defined by
[Gate 3 Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md):

```text
CanonicalReaderFactory.create
-> active validated CanonicalArtifactV1
-> Gate3ProjectionV1
-> exact selected managed dictionary and future instruction
-> Gate3LabelingResponseV1 proposal
-> code validation and alias restoration
-> label-only FinancialAnnotationsV1 intermediate
-> Gate3RoleLabelingResponseV1 proposal over the same chunk
-> code validation and source binding
-> FinancialAnnotationsV2
```

Gate 3 has one logical input, the exact active canonical version returned by
the public reader, and one current authoritative output, validated
`FinancialAnnotationsV2`. Projection, both model responses and the V1
label-only result are intermediate boundary contracts, not additional document
or financial authorities.

G3.1 defined these contracts. G3.2 implements the reader-backed
`Gate3ProjectionV1` adapter. G3.3M adds only the explicitly loaded
Managed Financial Label Dictionary v1 and its human-reviewed lifecycle. G3.4B
adds a non-persisted structural chunk set over the exact G3.2 render plan; it
does not change the projection schema or target grammar. G3.4C adds one thin,
sequential batch coordinator over the existing chunker and exact
G3.4 labeling/validation path. Its original live proof validated 11 of 12
selected chunks and preserved the remaining response as an explicit rejection.
G3.4D then validated the compact document and frozen large-CSV chunk with exact
bare aliases. The 2026-08-08 refinement adds one Role Pack-owned second pass
per non-empty chunk and advances current persistence to the compatible
`broker_reports_financial_annotations_v2` sidecar; V1 remains immutable
historical contract evidence.
G3.C5 activates these same G3.2-G3.5 owners only through the stable NDFL
Workspace Model/workflow. G3.6 remains a non-persisted, artifact-derived
`NDFL` case-readiness view and code-owned follow-up actions.

## 2. Ownership and boundaries

| Boundary | Owns | Does not own |
| --- | --- | --- |
| Gate 2 | normalized non-financial document structure, order, tables, provenance and issues | financial labels or a model-facing Gate 3 view |
| `Gate3ProjectionV1` | one deterministic Markdown view and backend-only aliases for existing canonical targets | financial meaning, source parsing or document repair |
| Managed Financial Label Dictionary v1 | exact published label IDs, meanings, application boundaries, examples and version lifecycle; stable Skill/Tool binding for generated OpenWebUI projections | canonical structure, target selection, model execution or workflow state |
| `Gate3LabelingResponseV1` | a sparse provider proposal of alias/label pairs | canonical refs, new labels, source rewriting or completion state |
| Managed Financial Role Pack v1 | role definitions, required/optional profiles, value-source and cardinality constraints | labels, canonical structure, provider execution or persistence |
| `Gate3RoleLabelingResponseV1` | one proposal for all pass-1 facts in a non-empty chunk; source alias bindings or explicit `missing` | relabeling, normalized/computed values, canonical IDs or relations |
| `FinancialAnnotationsV2` | validated canonical-target/type/role bindings plus reproduction identities | a rewritten document, Financial Domain, relations, calculations or tax meaning |
| current batch result | ordered terminal pass-1/pass-2 chunk outcomes plus deterministic concatenation of validated annotations | semantic reconciliation, per-fact calls, retry, repair or persistence |
| G3.5 persistence | full-document admission, exact active binding and immutable private ArtifactStore sidecar save/read | labeling, a second store, workflow state or product activation |
| G3.6 readiness | deterministic case/document completion and fixed follow-up permissions derived from existing artifacts | persisted state, financial meaning, LLM decisions or Gate 4 execution |
| NDFL workflow | exact validated-manifest selection, compare-and-swap activation, full-document Gate 3 coordination and exact sidecar handoff | any Gate 2 call to Gate 3, copied canonical payload, stage reimplementation, display-name routing or Gate 4 |

The exact [Managed Financial Label Dictionary v1](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md)
is the only owner of financial-label meaning. This contract names labels but
defines none. Skill, Prompt, Tool, generated view or model output must not
become a second meaning authority.

The exact Role Pack loaded by `Gate3FinancialRolePackFactory.create` is the
only owner of role IDs, per-label profiles and binding rules. Those rules must
not be copied into Python branches, prompts, Skills, adapters or RAG.

## 3. Normative schemas

- [`Gate3ProjectionV1`](./BROKER_REPORTS_GATE3_PROJECTION.v1.schema.json)
- [`Gate3LabelingResponseV1`](./BROKER_REPORTS_GATE3_LABELING_RESPONSE.v1.schema.json)
- [`FinancialAnnotationsV1`](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v1.schema.json)
- [`Gate3RoleLabelingResponseV1`](./BROKER_REPORTS_GATE3_ROLE_LABELING_RESPONSE.v1.schema.json)
- [`FinancialAnnotationsV2`](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json)
- [Gate 3 Financial Role Pack v1](./BROKER_REPORTS_GATE3_FINANCIAL_ROLE_PACK.v1.schema.json)
- shared [`Gate3CanonicalTargetV1`](./BROKER_REPORTS_GATE3_TARGET.v1.schema.json)

The shared target schema is a small boundary component, not a fourth stage
artifact. It prevents projection and annotations from defining independent
canonical-locator grammars.

All schemas are closed with `additionalProperties=false`. Fields not present in
these schemas are forbidden unless a later versioned contract proves they are
necessary.

## 4. Gate 2 input

The only allowed logical input is the exact artifact returned by
`CanonicalReaderFactory.create` for an authenticated document/context.
`canonical_binding` contains exactly:

```text
document_id
canonical_version_id
```

The reader and canonical version record remain the owners of schema, root hash,
source identity, physical layout and integrity accounting. Gate 3 does not copy
those fields into its minimal payload merely because they are available.

Gate 3 must not:

- open PDF, HTML, CSV or XLSX source bytes;
- read parser units, crops, raw provider output or physical canonical chunks;
- infer a format branch;
- mutate, repair or republish `CanonicalArtifactV1`;
- use `gate2_handoff_v0` as a fallback.

## 5. Gate3ProjectionV1

`Gate3ProjectionV1` is one internal envelope with two deliberately separated
parts:

1. `model_view`: only `text/markdown` content intended for the model;
2. `target_mappings`: backend-only reversible aliases.

Only `model_view` may be inserted into model-visible document context. The
mapping must remain code-owned and must not be exposed as canonical IDs.

An alias has the form `t` plus at least three decimal digits, for example
`t001`. `Gate3ProjectionFactory.create(document_id, context)` is the sole
construction entrypoint. It creates the public canonical reader and calls
`read_active_envelope`; callers cannot supply an artifact, source format or
physical layout directly.

The renderer walks the root container, then each container's canonical node
order followed by its child-container order. One monotonically increasing
counter assigns `t001`, `t002`, ... at the moment an addressable fragment is
rendered. The same canonical version and this contract therefore produce the
same Markdown and mapping.

Addressability is deliberately direct:

- `HEADING`, `TEXT` and `NOTE` each receive one `node` alias;
- every list item receives one `list_item` alias in array order;
- a table title or table note receives one shared `node` alias because neither
  has a smaller v1 locator;
- every row represented by at least one canonical cell receives one
  `table_row` alias;
- every canonical cell receives one `table_cell` alias in row/column order;
- page/sheet breaks and conflict/ambiguity nodes remain visible but receive no
  alias.

Containers become Markdown headings; text, lists, table titles, rows, cells,
notes, breaks and issue summaries remain in logical order. Canonical cell
display values are preferred, followed by cached, normalized and raw values.
Source brackets, table separators and line breaks are escaped so source text
cannot mint an alias or break the Markdown table. No provenance IDs, source
refs, storage fields or physical-layout data enter `model_view`.

The minimal canonical target kinds are:

| Kind | Canonical meaning |
| --- | --- |
| `node` | one existing `node_id` |
| `list_item` | zero-based item in an existing `LIST` node |
| `table_row` | one-based row represented by an existing `TABLE` node's cells |
| `table_cell` | one-based row and column represented by an existing `TABLE` cell |

No text-span locator, container locator or invented financial-fact ID exists in
v1. A target must resolve inside the exact bound canonical version. Break,
conflict and ambiguity nodes are not labelable financial facts.

The projection may expose zero or more aliases. An alias makes an existing
element addressable; it does not assert that the element is financial.

### 5.1 Bounded structural chunks

The full `Gate3ProjectionV1` remains the deterministic source projection.
`Gate3StructuralChunkFactory.create` may derive an ordered, non-persisted
`Gate3StructuralChunkSetV1` through the exact package-internal render plan owned
by `Gate3ProjectionFactory`.

The chunker keeps a complete projection whole when it fits its exact character
budget, otherwise keeps each table whole when possible and splits only an
oversized table into contiguous groups of whole rows. Alias-free ancestor
headings, table headings, headers and structurally attached notes may repeat as
context. Every original target alias and mapping remains working content in
exactly one chunk, with zero data-row overlap and preserved visible target
order.

The normative structural contract and closed schema are
[Structural Chunking v1](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNKING.v1.md) and
[Gate3StructuralChunkSetV1](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNK_SET.v1.schema.json).

## 6. Sparse labeling semantics

The model is not required to classify every alias or every document element.
It returns only financial labels it considers supported by the supplied
document view and exact dictionary:

```text
supported financial fact -> return target_alias + financial_label
not supported or uncertain -> omit the annotation
```

Absence has no stronger meaning. It does not mean `no_financial_input`,
`unsupported`, `unclassified`, complete coverage or a negative financial
decision. An empty `annotations` array is a valid provider proposal and may
produce a validated empty sidecar.

One canonical target may receive different allowed labels when the same
canonical element explicitly contains more than one financial fact. The exact
same target/label pair must not appear twice.

## 7. Gate3LabelingResponseV1

The model response contains exactly:

```text
schema_version
annotations[]:
  target_alias
  financial_label
```

It contains no canonical IDs, source values, copied document content,
confidence, reasoning, provenance, dictionary edits, calculated values or
workflow status. It is a proposal until code validates it.

`target_alias` is always the exact bare alias value. The G3.1/G3.2 alias
authority defines its form as `t` followed by at least three decimal digits;
the response schema projects that rule as `^t[0-9]{3,}$`. If the document shows
`[t123]`, the JSON field value is exactly `t123`. Brackets, Markdown, embedded
quotes, prefixes such as `target=` or `alias:`, angle brackets and explanatory
text are not part of the value and must be rejected rather than stripped.

The schema property description and the short G3.4 instruction are
model-facing projections of this existing grammar, not independent owners.
The provider schema must retain every supported explanatory keyword, must not
enumerate the current chunk aliases, and the deterministic validator must
still check exact membership in that chunk after the response.

The response schema validates the closed syntax. The G3.4 validator additionally
proves all dynamic invariants:

1. every alias exists exactly once in the bound projection mapping;
2. every label exists in the exact selected dictionary version;
3. every restored target exists in the exact canonical version;
4. every target kind matches the referenced canonical node/content shape;
5. no exact target/label pair is duplicated;
6. projection, dictionary and instruction identities belong to the same
   execution;
7. no provider field can alter canonical refs or financial-label meaning.

Schema validity alone is never semantic acceptance.

## 8. Historical label-only FinancialAnnotationsV1

`FinancialAnnotationsV1` is the validated pass-1 result and historical
label-only sidecar shape. Its payload
contains only:

```text
schema_version
canonical_binding:
  document_id
  canonical_version_id
dictionary_identity:
  dictionary_id
  semantic_version
instruction_identity:
  instruction_id
  semantic_version
model_identity:
  model_id
annotations[]:
  target
  financial_label
validation_status = validated
```

Temporary aliases are restored before this artifact is created and therefore
do not appear in it. `validation_status` is always `validated`; an unvalidated
provider response is not a `FinancialAnnotationsV1` artifact.

Artifact ID, case/chat/user scope, timestamps, retention, payload integrity and
purge state belong to the existing ArtifactStore envelope used by G3.5. They
are intentionally absent from this payload. Provider profile identity is also
stored in immutable envelope metadata because the closed v1 payload owns only
the exact `model_id`.

A later dictionary version may produce a different sidecar for the same
canonical version. The dictionary and instruction identities make the old
sidecar reproducible without mutating it.

The current persisted output is `FinancialAnnotationsV2`. Its role fields,
validation rules and deterministic consumption boundary are normative in
[Gate 3 Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md).

## 9. Positive examples

### 9.1 Projection

```json
{
  "schema_version": "broker_reports_gate3_projection_v1",
  "canonical_binding": {
    "document_id": "document-001",
    "canonical_version_id": "canonical-version-007"
  },
  "model_view": {
    "media_type": "text/markdown",
    "content": "## Fees\n\n[t001] Brokerage fee: 12.00 USD\n\n| Type | Amount |\n| --- | ---: |\n| [t002] Dividend | 100.00 USD |"
  },
  "target_mappings": [
    {
      "target_alias": "t001",
      "canonical_target": {
        "kind": "node",
        "node_id": "node-fee"
      }
    },
    {
      "target_alias": "t002",
      "canonical_target": {
        "kind": "table_cell",
        "node_id": "node-income-table",
        "row": 2,
        "column": 1
      }
    }
  ]
}
```

### 9.2 Sparse model response

```json
{
  "schema_version": "broker_reports_gate3_labeling_response_v1",
  "annotations": [
    {
      "target_alias": "t001",
      "financial_label": "BROKER_FEE"
    }
  ]
}
```

The omission of `t002` makes no negative claim. The following is also valid:

```json
{
  "schema_version": "broker_reports_gate3_labeling_response_v1",
  "annotations": []
}
```

### 9.3 Validated sidecar

```json
{
  "schema_version": "broker_reports_financial_annotations_v1",
  "canonical_binding": {
    "document_id": "document-001",
    "canonical_version_id": "canonical-version-007"
  },
  "dictionary_identity": {
    "dictionary_id": "broker-reports-financial-labels",
    "semantic_version": "1.0.0"
  },
  "instruction_identity": {
    "instruction_id": "broker-reports-bounded-semantic-labeling",
    "semantic_version": "1.0.1"
  },
  "model_identity": {
    "model_id": "model-exact-id"
  },
  "annotations": [
    {
      "target": {
        "kind": "node",
        "node_id": "node-fee"
      },
      "financial_label": "BROKER_FEE"
    }
  ],
  "validation_status": "validated"
}
```

## 10. Negative examples

| Candidate | Result | Owner of rejection |
| --- | --- | --- |
| response contains `confidence`, prose or `node_id` | reject | closed response schema |
| response uses an alias absent from the exact projection | reject | G3.4 validator |
| response returns `[t001]`, `` `t001` ``, `target=t001`, `alias: t001` or `<t001>` | reject without normalization | closed response schema and G3.4 validator |
| response uses a label absent from the exact dictionary | reject | G3.4 validator |
| identical alias/label pair occurs twice | reject | G3.4 validator |
| mapping points to a missing node, row, cell or list item | reject | G3.2 renderer; G3.4 response validator |
| mapping points to `CONFLICT`, `AMBIGUITY`, `PAGE_BREAK` or `SHEET_BREAK` | reject | G3.2 renderer; G3.4 response validator |
| sidecar binding differs from the reader-selected canonical version | reject | G3.5 writer |
| sidecar says `pending`, `blocked` or any status other than `validated` | reject | FinancialAnnotations schema |
| provider returns no annotations | accept as empty proposal | response schema and future validator |

Rejected provider output must never be repaired into a successful annotation
artifact by adding a label, changing an alias or switching canonical versions.

## 11. Compatibility with CanonicalArtifactV1

The target grammar uses only identities already present in
`CanonicalArtifactV1`:

- `nodes[].node_id`;
- `nodes[].content.items[]` array position for a `LIST` node;
- `nodes[].content.cells[].row` and `.column` for a `TABLE` node.

It introduces no field into the canonical schema. A projection or sidecar is
invalid if the referenced target cannot be resolved against the exact bound
canonical version.

The same grammar is used before and after alias restoration. Projection stores
`target_alias -> canonical_target`; FinancialAnnotations stores that restored
`canonical_target -> financial_label` directly.

## 12. Explicit non-goals

The current G3.1-G3.6 contour does not implement or authorize:

- any dictionary version other than an explicitly reviewed and hash-pinned
  package resource;
- a Prompt-owned definition copy, Knowledge/RAG source or model-invoked semantic Tool call; the G3.C1 Skill/Tool remain generated management projections of the package owner;
- retry, response repair, fallback or provider qualification;
- alias stripping, regex extraction, best-effort parsing or an alias normalizer;
- a second persistence store, projection cache or projection database;
- persisted workflow state, LLM-owned readiness or LLM-owned actions;
- exhaustive classification or coverage claims;
- Financial Domain, records, cross-fact relations, graph or Gate 4 materialization;
- calculations, reconciliation, tax meaning or Gate 4;
- product canonical-read cutover outside the stable NDFL route, global runtime
  activation or destructive legacy deletion.

## 13. Stop condition and next allowed GOAL

The G3.1 stop condition is satisfied: `node_id`, list-item position, and table
row/cell coordinates provide reversible locators for existing canonical
elements without changing Gate 2. Text-span annotations remain deliberately
outside v1; if a future real case cannot be represented by the existing target
kinds, that case must stop rather than invent a hidden span grammar.

The G3.2 stop condition is satisfied: the public reader provides all logical
content needed for deterministic Markdown and reversible aliases across PDF,
HTML, CSV and XLSX. No source-file reread or Gate 2 change is required.

The G3.3M stop condition is satisfied: the exact nine-label dictionary has one
normative owner, immutable v1 identity, explicit loading, deterministic full
rendering and a draft/diff/approval/publish-preparation lifecycle. Published v1
is active only inside NDFL and never performs labeling independently.

G3.4B's stop condition is satisfied: the representative compact HTML,
large one-table CSV and REPO XLSX shapes are bounded with exact target coverage,
zero data-row overlap and no provider call.

G3.4C's live route proof is partial: 11 of 12 selected chunks validated, the
schema adapter fix was proven on every request, and the 60,000-character bound
reduced the large-CSV peak input by 79.399008%. One compact response was
rejected because it returned bracketed display aliases instead of the exact
bare aliases. No retry or repair occurred. Manual semantic quality is
`PARTIAL`; positive accrued-coupon-component and securities-lending coverage
remain unproven.

G3.4D makes the existing output contract unambiguous without changing its
grammar: the canonical schema still enforces `^t[0-9]{3,}$`, its exact bare
alias description is projected through the existing provider adapter, and
instruction version `1.0.1` states `[t123] -> t123`. The bounded live closeout
validated the complete compact document and the frozen large-CSV chunk with
two submissions and zero retry, repair or fallback.

G3.5 persists only a `document_status=complete`, all-chunk validated result.
`Gate3FinancialAnnotationsPersistenceFactory.create` rechecks the exact active
canonical binding and known targets through the existing structural owner,
loads the exact published dictionary, checks instruction/model/provider
identity, inherits canonical-manifest retention, and delegates immutable
private payload save/read/access/purge to ArtifactStore and ArtifactResolver.
The live proof stored and read back five annotations, denied a wrong-user read,
rejected overwrite and preserved the exact Gate 2 version/root hash.

G3.6 derives one `NDFL` case snapshot through
`Gate3NdflCaseReadinessFactory.create(context)`. It requires current active
canonical versions and readable complete sidecars bound to those exact
versions, treats stale/incomplete sidecars as not ready, and permits
`PREPARE_DECLARATION` only when every document is Gate 3 ready. The live proof
derived 16 Gate 2-ready documents and one Gate 3-ready document, kept the
handoff disabled, and left the ArtifactStore byte-identical.

G3.7A completed the missing large-document path under the final strict
contract: all six chunks validated once, deterministic merge produced a
complete result, persistence/read-back passed and Gate 2 stayed unchanged.
G3.7B proved representative semantic quality `SUFFICIENT_FOR_MVP`, with seven
labels observed, important counterexamples/omissions distinguished and two
rare labels explicitly `NOT_MEASURED`.

G3.7C corrected the terminal scope: tax-case/corpus completion is downstream
state, not acceptance of the Gate 3 semantic-labeling mechanism. Its historical
audit observed `2/16`; processing all 16 documents is not a Gate 3 acceptance
criterion.

The separately authorized product-integration chain supersedes the former
Gate 4 continuation at this boundary. G3.C1-G3.C5 passed for the historical
label-only revision. The 2026-08-08 role refinement keeps the same NDFL route,
projection, chunks, aliases, provider factory and persistence owner, adds one
role proposal per non-empty chunk, and makes `FinancialAnnotationsV2` the
current downstream-ready sidecar. This contract did not start Gate 4; Gate 4
later closed under the separate current Pipeline Gates authority.
