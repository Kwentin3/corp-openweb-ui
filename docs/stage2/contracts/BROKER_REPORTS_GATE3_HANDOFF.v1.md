# Broker Reports Gate 3 Handoff v1

Status: `CURRENT_BOUNDARY`; Gate 3 implementation is `NOT_STARTED`

Date: 2026-08-06

This document defines only the boundary prepared by Gate 2. It does not
authorize Wave 2, global canonical reads, a product cutover or financial logic.

## Input contract

```text
CanonicalReaderFactory.create
-> active validated CanonicalArtifactV1
-> future task-specific LLM-friendly projection
-> Gate 3
```

The caller supplies an authenticated document identity/context to the public
reader. It does not supply PDF, HTML, CSV, XLSX, parser units or a format flag.
The future Gate 3 adapter may consume ordered containers, nodes, tables, issues
and provenance from the reader result.

## Guarantees already provided by Gate 2

- one versioned public schema and one reader;
- deterministic order and common table-cell semantics;
- validated source/root/container/node references;
- fail-closed meaningful-content completeness;
- immutable version publication and atomic active pointer;
- component and root verification after reconstruction;
- compact provenance linked to the authenticated source;
- explicit conflicts, ambiguities and unsupported-feature issues;
- no provider result promoted directly to canonical truth.

`CanonicalArtifactV1` is the source of truth for the normalized non-financial
machine projection. Original bytes and Full Evidence remain audit truth behind
their authenticated Gate 1 boundary; Gate 3 follows provenance through an
authorized service when investigation is required and must not read private
evidence directly.

## Gate 3 obligations

Gate 3 must create and version its own task-specific projection/semantic
contract without modifying canonical source meaning. It must preserve links to
canonical version and provenance, propagate blocking issues, and treat
conflicts/ambiguities as unresolved rather than facts.

Gate 3 must not:

- parse the original file or branch on its format;
- reconstruct PDF order, XLSX sheets or source tables;
- call VLM/table proposals as authority;
- normalize document structure again;
- interpret literal labels, headings, cells, amounts or dates as already
  classified financial semantics;
- bypass `CanonicalReaderFactory`, read physical layouts or use silent legacy
  fallback.

The existing `render_neutral_canonical_projection` helper proves format-neutral
traversal only. It is not the future LLM-friendly product projection and must
not be promoted into Gate 3 without a separate contract and authorization.
