# Broker Reports GOAL G3.2 — LLM-Friendly Projection

Status: `COMPLETED`

Date: 2026-08-07

Scope: inactive, deterministic projection from the exact active
`CanonicalArtifactV1` version. No dictionary, model call, persistence,
OpenWebUI workflow, product activation or G3.3 work was performed.

## GOAL_STATUS

```text
GOAL_STATUS = COMPLETED
NEXT_ALLOWED_GOAL = G3.3 — Managed Financial Dictionary
```

## WHAT_WAS_ACHIEVED

The repository now has one inactive construction route:

```text
Gate3ProjectionFactory.create(document_id, context)
-> CanonicalReaderFactory.create
-> read_active_envelope
-> deterministic Markdown model_view
+ backend-only reversible target_mappings
-> Gate3ProjectionV1
```

The renderer preserves the canonical container/node order and presents
headings, text, lists, tables, rows, cells, notes, breaks and issue summaries
without reopening the source file. Aliases are deterministic, appear exactly
once in model-visible Markdown, and resolve to the exact bound canonical
version. Conflict, ambiguity and break nodes remain visible but cannot become
label targets.

PDF, HTML, CSV and XLSX use the same renderer and public reader path. Both
single-payload and chunked canonical storage layouts were verified without a
layout branch in Gate 3.

## WHAT_WAS_REUSED

- `CanonicalReaderFactory.create().read_active_envelope` as the sole input
  boundary;
- the unchanged `CanonicalArtifactV1` and its validator;
- the G3.1 `Gate3ProjectionV1` and shared `Gate3CanonicalTargetV1` schemas;
- canonical node IDs, list positions and table row/cell coordinates;
- existing ArtifactStore tenancy, version selection and integrity checks;
- the existing GitHub Broker Reports CI job.

The DOC33 `render_neutral_canonical_projection` remains independent
completeness proof tooling. It was not promoted or turned into a second Gate 3
authority.

## WHAT_WAS_ADDED

- one maintained module, `broker_reports_gate1/gate3_projection.py`;
- one public `Gate3ProjectionFactory.create` entrypoint;
- deterministic Markdown rendering and one internal sequential alias issuer;
- fail-closed mapping validation against the exact reader-returned artifact;
- behavioral tests using real SQLite ArtifactStore publication, activation and
  reader reconstruction;
- CI registration for the G3.1 contract and G3.2 projection suites;
- exact G3.2 authority, handoff, reader and contract documentation.

No new DTO class, config object, schema version, service layer, dependency,
database, artifact type, registry, cache or persisted receipt was added.

## WHAT_WAS_CONSCIOUSLY_NOT_DONE

- no financial dictionary or financial-label meaning;
- no Prompt, Skill, Tool, Knowledge or RAG path;
- no LLM/provider call, retry, repair, fallback or qualification;
- no `FinancialAnnotationsV1` construction or persistence;
- no projection storage or batching layer;
- no source-file, parser payload, crop or private-evidence read;
- no Gate 2 mutation, canonical republish or product read cutover;
- no Financial Domain, workflow, Gate 4 or legacy deletion;
- no G3.3 implementation.

## ACCEPTANCE_EVIDENCE

Focused G3.2 behavior:

```text
5 passed in 1.59s
```

Contract, architecture and authority verification:

```text
50 passed in 37.31s
45 passed in 29.57s
```

The first full offline run found one real closed-world declaration gap after
executing all tests:

```text
1 failed, 2689 passed, 5 skipped, 1 deselected
```

The new package module was then declared as a standalone contract authority and
its suite was added to CI. The final full offline service run passed:

```text
2690 passed, 5 skipped, 1 deselected in 913.13s
```

The deselected test is the pre-existing Windows CRLF-only generated-bundle raw
byte comparison. G3.2 changes no generated bundle or maintained bundle input.

Additional checks:

```text
ruff E9/F63/F7/F82 = passed
git diff --check = passed
all G3.1 schemas and the authority proof JSON parsed = passed
authority-map normalized LF SHA-256 pin = matched
isolated copied-package import of Gate3ProjectionFactory = passed
provider calls = 0
stage mutations = 0
```

Test state was isolated through a separate `tmp_path` SQLite database and
payload root per behavioral test. The tested G3.2 operation is read-only and
returns one synchronous projection dict; it has no irreversible boundary.

## KNOWN_LIMITATIONS

- G3.2 does not test model comprehension or labeling quality; that belongs to
  G3.4 after a dictionary exists.
- Projection is intentionally in-memory and unbatched. A demonstrated document
  size blocker is required before adding batching or storage.
- v1 has no text-span target. Table notes share the table node target because
  the current target grammar has no smaller locator.
- Empty canonical documents correctly produce a terminal projection with zero
  aliases; omission makes no financial or completeness claim.
- Runtime/product reachability remains absent. The explicit reader enablement
  used by tests is not a product flag or activation.

## KISS_CHECK

1. **Could this be simpler?** Not without losing the required Markdown or
   reversible aliases. The existing neutral renderer has a different proof
   ownership and no target mapping.
2. **Was a layer added that current behavior does not need?** No. One module
   and one factory method construct the required projection directly.
3. **Was a second source of truth created?** No. Canonical structure stays in
   Gate 2; target grammar stays in the G3.1 schemas; G3.2 only renders them.
4. **Was anything added only for possible future use?** No. There is no cache,
   persistence, batching, provider seam, dictionary abstraction or workflow.
5. **Can the result be explained simply?** Yes: code reads one validated
   canonical document, renders compact Markdown, and gives its addressable
   fragments short reversible aliases.

## NEXT_ALLOWED_GOAL

```text
G3.3 — Managed Financial Dictionary
```

G3.3 was not started.
