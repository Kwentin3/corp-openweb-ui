# Broker Reports Gate 1 document memory v1

Status: authoritative public-boundary refinement

Root schema: `broker_reports_gate1_document_memory_manifest_v1`

Policy: `broker_reports_gate1_document_memory_policy_v1`

Profile: `broker_reports_gate1_source_evidence_profile_v1`

## Decision

The document-memory root is a small safe manifest over the maintained Gate 1
artifact graph. It does not replace DCP, the issue ledger, source payloads,
source units, normalized-table projections or ArtifactStore. It gives those
existing artifacts one authoritative cohesion and completeness root.

```text
case scope
  -> source file ref
     -> one v1 logical document ref
        -> private normalized source payload refs
        -> private normalized source unit refs
        -> private normalized table projection refs
        -> source scope and counts
        -> issue refs
        -> completeness/accounting status
```

The root is persisted as `safe_internal`. Customer source values and normalized
content remain `private_case` and are resolved only through scoped
`ArtifactResolver` access.

## Identity and cohesion

For every source file entry the root records:

- `source_file_ref` and a checksum-derived safe reference;
- exactly one deterministic `logical_document_ref` for profile v1;
- the producing `normalization_run_id` and profile variant;
- typed refs to all normalized payloads, source units and table projections;
- a deterministic source-scope reference and declared/normalized counts;
- linked issue ids, terminal status and zero-silent-loss result;
- Gate 2 readiness without exposing private values.

The validator rejects missing or duplicate source identities, a logical-document
count other than one, duplicate normalized-artifact refs, private field names in
the safe root, a changed integrity hash, and any root that cannot be rebuilt
exactly from the maintained package graph.

One source file may produce many private payloads/units/projections, but none is
an orphan: each unit points to its parent payload and every public ref remains
traversable through source file, logical document, run and scoped ArtifactStore
context.

## Completeness and zero silent loss

The declared scope counts source files, logical documents, content artifacts,
rows, cells, text characters, PDF pages and normalized tables. The accounting
validator additionally proves:

- payload and source-unit counts match the full-source summary;
- the set of payload-declared unit refs exactly equals the persisted unit set;
- every unit has an existing parent payload;
- selected refs have no unaccounted or duplicate members;
- every table projection passes its coverage validator;
- every native CSV/HTML table unit has a common table projection;
- row, cell and text-character counts match for non-PDF containers;
- PDF page count equals pages-with-text plus pages-without-text;
- no artifact ref is duplicated in the document graph.

Only `complete` and `review_required` can be profile-accepted. Either state must
also have `accounting_status=passed` and `zero_silent_loss=passed`; otherwise the
root is downgraded to `partial` and Gate 2 is blocked.

`review_required` is intentionally narrow: the source memory and fallback
lineage are complete, while a structural interpretation such as PDF table
topology remains unresolved. It does not authorize financial interpretation or
pretend that an unvalidated table is canonical.

## Public Gate 1 to Gate 2 handoff

The DCP contains a `document_memory_boundary` referring to the persisted root.
Gate 2 input readiness receives the DCP ref and an access context, then:

1. resolves DCP and root through `ArtifactResolver`;
2. validates the root using only `gate1_public_contracts`;
3. denies incomplete/unsupported documents and propagates issue/scope context;
4. discovers typed source units and table projections by refs;
5. emits bounded Gate 2 packages without importing a format parser.

Gate 2 must not import CSV, HTML, PDF, spreadsheet or concrete store internals.
The architecture test treats `document_memory.py` as Gate 1 private
implementation and enforces the public-contract/resolver dependency direction.

## Immutability, lifecycle and data policy

- Artifact records are append-only/immutable. Gate 2 adds its own artifacts and
  cannot rewrite the Gate 1 root or private payloads.
- Access is scoped by user, case-or-chat, workspace model, run, lifecycle and
  retention context; wrong context fails closed.
- Source deletion purges source-linked private artifacts while retaining only
  approved safe metadata required for audit/lifecycle evidence.
- Case purge makes the root unresolvable.
- No source values are persisted in chat history, Knowledge/RAG/vector storage,
  logs or the safe root.
- The integrity hash covers the complete safe manifest except the hash field
  itself.

## What each supported adapter contributes

| Adapter | Private memory | Common public consumption |
| --- | --- | --- |
| CSV | whole-file tabular payload, ordered row-window units, source values/cells | validated normalized-table refs plus scope/issues |
| static HTML | ordered text/table payloads and units | normalized text units and validated normalized-table refs |
| text-layer PDF | page/text payload, layout/line/table-candidate units and validated projections where possible | format-independent text/table units with page/layout provenance and explicit unresolved issues |

Gate 1 records technical representation only. Income, trade, commission, tax,
deduction and declaration-field classification remain exclusively Gate 2 or
later responsibilities.

