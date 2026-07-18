# Broker Reports Gate 1 document memory v1

Status: authoritative public-boundary contract; actual-corpus validated

Root schema: `broker_reports_gate1_document_memory_manifest_v1`

Policy: `broker_reports_gate1_document_memory_policy_v1`

Profile: `broker_reports_gate1_source_evidence_profile_v1`

## Decision

The document-memory root is the safe cohesion and completeness authority over
the maintained Gate 1 artifact graph. It does not replace private normalized
payloads, source units, table projections, the issue ledger, DCP or
ArtifactStore. It links them without exposing customer values.

```text
case / normalization run
  -> source file
     -> optional archive-container lineage
        -> promoted member source file
     -> logical document
        -> normalized payload refs
        -> text / table / visual source-unit refs
        -> validated table-projection refs
        -> declared and normalized scope
        -> issue refs and restrictions
        -> terminal/accounting/zero-loss status
```

The root is `safe_internal`. Customer text, rows, cells, media and normalized
private values remain `private_case` and are accessible only through scoped
`ArtifactResolver` calls.

## Identity and cohesion

Every entry records a safe source/checksum identity, producing run/profile,
logical-document policy, normalized artifact refs, scope counts, issue refs,
terminal status and Gate 2 scope readiness.

- A non-ZIP source record has exactly one deterministic logical-document ref.
- A ZIP container has zero logical documents and `lineage_only` readiness.
- Each promoted ZIP member is a new source record with exactly one logical
  document and explicit parent/member lineage.
- Every unit points to one parent payload.
- Every safe artifact ref is unique and resolvable in its run/context.

The validator rejects missing/duplicate identities, invalid logical-document
counts, orphan units, duplicate artifact refs, private fields, integrity-hash
drift or any root that cannot be rebuilt from the maintained package graph.

## Normalized scopes

The root accounts for:

- source files and logical documents;
- archive members, promoted members and signature sidecars;
- text characters and DOM/content order;
- rows, cells and normalized tables;
- PDF pages, page text/layout and bounded visual pages;
- HTML bounded visual-media items;
- neutral ordered XML events;
- validated projections and explicitly unavailable canonical scopes.

Visual units are memory, but require a visual-aware consumer. Neutral XML
memory is structurally ready, but does not claim financial semantics. A
blocked table projection is not published as canonical; the underlying
text/layout/visual lineage and restriction remain explicit.

## Completeness and zero silent loss

Only `complete` and `review_required` are profile-accepted. Both require
`accounting_status=passed` and `zero_silent_loss=passed`. Otherwise the entry
is downgraded to `partial` and its Gate 2 memory is blocked.

Accounting proves at least:

- payload/unit counts equal full-source declarations;
- payload-declared unit refs equal the persisted unit set;
- every unit has a parent payload;
- selected refs have no unaccounted or duplicated members;
- native CSV/HTML/XML tables have common projections;
- rows, cells, text, visual items and archive members match declared scope;
- PDF page count and text/visual coverage reconcile;
- every published table projection passes its own validator;
- no source or normalized artifact is silently omitted.

`review_required` is not a degraded success label. It is a precise contract:
the memory is complete, while a named interpretation scope remains restricted.

## Public Gate 1 -> Gate 2 handoff

DCP carries `document_memory_boundary` with manifest schema/id/integrity hash,
profile id, resolver requirement and
`format_specific_parser_required_by_gate2=false`.

The required public audit:

1. resolves DCP and the memory root through `ArtifactResolver`;
2. validates manifest integrity and profile enforcement;
3. reads only typed refs and per-scope readiness;
4. denies blocked/unready scopes;
5. never imports CSV, HTML, PDF, XML or ZIP parsers into Gate 2;
6. leaves the Gate 1 ArtifactStore catalog unchanged.

The actual-corpus proof passed all boundary checks for 104 source records. A
full mass build of every optional Gate 2 package was not part of the Gate 1
acceptance boundary. Its previously observed long runtime is recorded as a
separate bounded-performance debt; it is not evidence of Gate 1 data loss.

## Immutability, lifecycle and privacy

- Artifact records are immutable and append-only.
- Access is scoped by user, case/chat, workspace model, run, lifecycle and
  retention context; a wrong context fails closed.
- Source deletion purges source-linked private artifacts under the maintained
  lifecycle policy while retaining approved safe audit metadata.
- Case purge makes the root unresolvable.
- No source values are stored in chat history, safe reports,
  Knowledge/RAG/vector storage or Git.
- The manifest integrity hash covers the safe root except its own hash field.

## Adapter contributions

| Adapter | Private memory | Public consumption |
| --- | --- | --- |
| CSV | ordered row/source-value units | validated table refs and scope |
| HTML | DOM-ordered text/table blocks and bounded visual media | text/table refs, visual restriction and issues |
| PDF | page text/layout, table candidates and bounded visual pages | page/text/table scopes with provenance and explicit fallback |
| XML | ordered neutral event rows | neutral-structure scope; canonical financial table unavailable |
| ZIP | safe member inventory and promoted-member lineage | lineage-only container plus ordinary member document roots |

Gate 1 owns representation. Income, trade, fee, tax, deduction and declaration
semantics remain Gate 2 or later responsibilities.

## Evidence

- Actual proof run: `normrun_e1855c54126bce9c`.
- Accepted source records: 104.
- Logical documents: 80.
- Terminal states: 26 `complete`, 78 `review_required`, zero other states.
- Safe evidence:
  `docs/reports/2026-07-18/BROKER_REPORTS_GATE1_ACTUAL_CUSTOMER_CORPUS_ACCEPTANCE.v1.safe.json`.
