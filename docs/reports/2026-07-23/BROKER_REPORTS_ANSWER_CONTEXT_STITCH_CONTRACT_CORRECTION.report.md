# Broker Reports — Answer Context Stitch Contract Correction

Date: 2026-07-23

Branch: `codex/broker-reports-answer-context-stitch-contract-v1`

Implementation status: `PASSED`

Live release status: `PENDING_AFTER_MERGE`

## Failure attribution

The final full suite detected one production anti-drift violation:

```text
expected: []
actual: [answer_context_selection->gate2_source_fact_stitching]
```

The shared answer-context layer imported a schema identity from Gate 2 business
runtime. The artifact format was valid, but the dependency direction violated
the accepted Gate boundary.

## Narrow correction

- Added the unchanged stitch-result schema identity to neutral `contracts.py`.
- Kept `STITCH_RESULT_SCHEMA_VERSION` as an exact compatibility alias in Gate 2
  stitching.
- Made answer-context validation depend only on the neutral contract identity.
- Removed one pre-existing unused import from the touched stitching module.
- Regenerated all three maintained closed-world Function bundles.

The stitch schema literal, stored artifact type, answer-context format, owner
filter, fact identities, semantic JSON contract, prompts and provider behavior
are unchanged.

Canonical routes and anti-drift anchors:

- `answer_context_selection.py:30` —
  `AnswerContextSelectionFactory.create`;
- `answer_context_selection.py:31` — raw source/crop/provider/RAG/duplicate
  representations remain forbidden;
- `gate2_source_fact_stitching.py:15` —
  `Gate2SourceFactStitcherFactory.create`;
- `gate2_source_fact_stitching.py:18` — non-stitching callers remain forbidden
  from resolving ownership.

The three generated bundles contain the neutral contract and do not contain the
removed answer-context import from Gate 2 stitching. This is the closed-world
artifact used by OpenWebUI Functions; no workspace-only import or filesystem
path dependency was introduced.

## Verification

Focused behavior and architecture:

```text
27 passed
```

Full service suite, PowerShell from the service root:

```text
collected: 1154
passed: 1134
failed: 0
skipped: 20
xfailed/xpassed: 0
warnings: 5
duration: 92.00 s
```

All skips are the declared offline private benchmark cases.

Additional privacy, architecture and integrated reproof:

```text
15 passed
```

Changed maintained Python files:

- Ruff: passed;
- compileall: passed;
- import check: passed;
- legacy stitch schema alias: exact.

An exploratory unconfigured repo-wide Ruff invocation reported existing legacy
diagnostics in re-export and test-bootstrap files. The repository has no global
Broker Reports Ruff configuration; the accepted historical command is Ruff on
changed maintained Python files. No unrelated lint rewrite was mixed into this
correction.

## Deterministic bundles

Two consecutive `--target all` generations were byte-identical:

| Function bundle | SHA-256 |
|---|---|
| Gate 1 | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` |
| Gate 2 source | `a6df7853e7cf40676fd4483feeac0d8d136b2121967e6f0df39f8d85324df32a` |
| Gate 2 domain | `1bb11d428cb9082edec388109839e7f2f3117447daefe9470129bc2413ed1499` |

`git diff --check`: passed.

Stage mutation in this branch: 0.

An atomic release of the exact merged revision and rollback/readback proof are
required before the correction is live-complete.
