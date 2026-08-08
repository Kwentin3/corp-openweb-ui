# Broker Reports Gate 3 Handoff v1

Status: `CURRENT SUPPORTING DOC`

Gate 3 status: `CLOSED`

Updated: 2026-08-08

This is the short recovery document for an agent approaching Gate 4 without
conversation history. It explains the accepted handoff; it does not own gate
numbering. The sole pipeline authority is
[Broker Reports Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md).

## Mental model

```text
Gate 1
-> stores the authenticated source and its stable identity

Gate 2
-> creates and stores an immutable validated CanonicalArtifactV1 version

NDFL workflow
-> selects one exact canonical manifest/version by stable identity

Gate 3
-> reads that version through CanonicalReaderFactory.create
-> creates structural chunks when needed
-> selects only known financial labels
-> binds selected facts to source-backed roles from one versioned Role Pack
-> stores a separate immutable FinancialAnnotationsV2 sidecar

Gate 4
-> G4.1 defines one minimal Gate4FinancialCaseFactV1 contract
-> materialization, SQL, case assembly and relations are not started
```

## What is closed

Gate 3 financial semantic and role labeling is closed and active only in the
NDFL product route. Pass 1 makes sparse dictionary-bound type proposals. Pass
2 runs once for all pass-1 facts in the same non-empty chunk, uses the exact
same aliases plus the complete Role Pack, and returns source bindings or
explicit `missing`. The backend validates both passes, merges deterministically
and persists one immutable sidecar.

Gate 3 does not mutate Gate 2, calculate tax, determine cost basis/FIFO,
reconcile multiple documents, prepare a declaration or implement Gate 4. Each
document is labeled independently. An omitted annotation is not a negative
claim.

## Exact Gate 2 -> Gate 3 handoff

```text
NdflWorkflowFactory.create().run_product_path(manifest_ref, context)
-> CanonicalReaderFactory.create().read_envelope(exact manifest_ref, context)
-> require VALIDATED or the exact already-ACTIVE canonical version
-> compare-and-swap activation when required
-> pass only document_id + authenticated ArtifactAccessContext to Gate 3
-> Gate3ChunkBatchLabelingFactory.create
   -> Gate3BoundedLabelingFactory.create_from_chunk (financial type)
   -> Gate3RoleLabelingFactory.create_from_chunk (roles; skipped if no facts)
-> Gate3FinancialAnnotationsPersistenceFactory.create
-> FinancialAnnotationsV2 bound to the exact canonical version
-> verify canonical version/root/payload unchanged after Gate 3
```

The handoff is persisted artifact identity. It is never “Gate 2 passes text to
Gate 3”, a caller-supplied canonical payload, chat completion or Pipe-to-Pipe
transfer. Gate 3 does not read original formats, parser units, physical layouts
or private evidence.

If active canonical version A changes to B during labeling, persistence fails.
If annotations A already exist when B becomes active, annotations A are stale
for current-version use and B requires its own annotations.

## Managed financial dictionary

The sole meaning owner is:

```text
broker-reports-financial-labels@<version>
current published identity: broker-reports-financial-labels@1.0.0
```

Operator path:

```text
OpenWebUI -> Workspace -> Skills -> Broker Reports Financial Labels
```

The runtime loads the pinned package resource through
`Gate3FinancialLabelDictionaryFactory.create`. Generated Skill and Tool assets
are exact projections of that owner:

- Skill stable ID: `broker-reports-financial-labels`;
- Tool stable ID: `broker_reports_financial_label_dictionary`;
- Tool method: `load_financial_label_dictionary`.

Do not create a second definitions copy in Python, Prompt, Skill, Tool or
Knowledge/RAG. Display names are UI text, not lookup or routing authority.

## Managed financial Role Pack

The sole role/profile owner is:

```text
broker-reports-financial-roles@<version>
current published identity: broker-reports-financial-roles@1.0.0
```

`Gate3FinancialRolePackFactory.create` loads the exact hash-pinned package
resource. It owns role definitions, each financial label's required and
optional roles, maximum-one cardinality, literal source binding and the ban on
normalized/computed values. Prompt, Skill, adapter and Python control flow must
not contain independent role/profile copies.

## NDFL product topology

| Role | Stable identity | Rule |
| --- | --- | --- |
| user entrypoint | Workspace Model `broker-reports-ndfl` | the one user-facing NDFL product |
| workflow | `broker-reports-ndfl` | owns the exact Gate 2 -> Gate 3 decision |
| technical base Pipe | `broker_reports_gate1_pipe` | internal OpenWebUI runtime base, not a second product |
| dictionary | `broker-reports-financial-labels@1.0.0` | one versioned meaning owner |
| Role Pack | `broker-reports-financial-roles@1.0.0` | one versioned role/profile owner |

## What Gate 4 may rely on

Gate 4 may rely on a validated `CanonicalArtifactV1`, its exact immutable
identity and a matching immutable `FinancialAnnotationsV2`. It may treat sparse
annotations only as positive known-label claims. For every selected fact it
may mechanically resolve each role binding to canonical target text or its
validated literal `exact_text`; it must preserve explicit `missing`.

Gate 4 must not reinterpret Gate 3 as tax calculation, infer absence from an
omitted label, attach annotations A to canonical version B, mutate either
upstream artifact, bypass the canonical reader, duplicate the financial
dictionary or reimplement Gate 3 labeling.

The current G4.1 boundary is
[Gate 4 Financial Case Fact v1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md).
It reuses the existing OpenWebUI-injected `ArtifactAccessContext` case/chat
scope, ArtifactStore lifecycle, exact Gate 3 artifact identity and shared
target grammar. It defines no materializer, SQL cache, relation layer or active
product route. G4.2 is the next allowed implementation Goal.

## Direct contracts and audit evidence

Read direct upstream contracts before implementation:

- [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md);
- [Canonical Artifact v1](./BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md);
- [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md);
- [Gate 3 Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md);
- [Gate 3 Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md);
- [FinancialAnnotationsV2 schema](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json);
- [Financial Label Dictionary v1](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md);
- [Gate 4 Financial Case Fact v1](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md).

Use reports only when auditing evidence:

- [corrected terminal Gate 3 proof](../../reports/2026-08-07/BROKER_REPORTS_GATE3_CORRECTED_TERMINAL_G3_7C.report.md);
- [real NDFL product-path proof](../../reports/2026-08-07/BROKER_REPORTS_GATE3_REAL_NDFL_PRODUCT_PATH_G3_C5.report.md);
- [managed dictionary OpenWebUI binding](../../reports/2026-08-07/BROKER_REPORTS_GATE3_MANAGED_DICTIONARY_OPENWEBUI_BINDING_G3_C1.report.md).
- [Gate 3 role-labeling closure](../../reports/2026-08-08/BROKER_REPORTS_GATE3_ROLE_LABELING_CLOSURE.report.md).

The actual `broker-reports-ndfl` product route end to end was exercised by the
G3.C5 proof; this is evidence for the one stable-ID route, not authority for a
second product or for Gate 4 runtime activation.

The earlier G3.7 terminal report is superseded by G3.7C. All dated reports are
evidence for their own revision and scope; none can override the current
pipeline contract.
