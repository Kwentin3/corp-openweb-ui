# Broker Reports Goal 3 — Gate 1 Bounded Graph Lifetime

Date: 2026-07-21
Status: `PASSED`
Implementation revision: `7e0316f035015c4a24d93ab3f938571bd8590bed`

## Verdict

Gate 1 now has a maintained document-bounded lifetime for heavy neutral
representations. The production Pipe and the actual-corpus proof construct one
document graph, validate it, persist final ArtifactStore records through
`Gate1BoundedGraphFactory`, retain compact refs/accounting receipts, and release
the decoded document graph before processing the next document.

The target is closed for the qualified actual-corpus contour:

- `GATE1_OUTPUT_EQUIVALENCE: PASSED`
- `GATE1_PEAK_RSS: AT_OR_BELOW_5_GIB`
- `INTERMEDIATE_LIFETIME: BOUNDED`
- `SOURCE_LOSS: ZERO`
- `REPRESENTATION_LOSS: ZERO`
- `ARTIFACTSTORE_CONTRACT: PRESERVED`

No representation was truncated, sampled or removed. Garbage collection is not
the lifetime boundary.

## Maintained architecture

`Gate1BoundedGraphFactory.create` is the only production construction route.
Each source identity and private representation is validated before append-only
persistence. The in-process compatibility collections inherit no heavy list
storage: their physical list remains empty while logical access is backed by
ArtifactStore refs. Deep copy of an unsealed view fails closed; deep copy after
seal preserves the immutable view.

Document-memory construction and final run validation use compact
pre-validation receipts containing only refs, counts and statuses. A
content-bearing consumer resolves at most one document at a time. Gate 2 reuses
the already-persisted records and is not allowed to mutate Gate 1 storage.

## Actual-corpus proof

The equivalence store was produced from the immediate pre-Goal-3 revision
`17da0ae385fe6c9ba93ddc858f9c55da6ba2611a`. The resource baseline remains the
accepted revision `f0e0c4a023f3e5bcf85c5797f039b102c11702f2`. The profiler now
requires the equivalence store explicitly; heuristic baseline selection is
forbidden.

| Measure | Baseline | Candidate | Result |
| --- | ---: | ---: | --- |
| Peak process RSS | 7,041,015,808 B | 712,183,808 B | −89.885%; passed 5 GiB limit |
| Full proof wall | 851.643532 s | 887.812302 s | +4.247%; passed +15% limit |
| Normalization checkpoint | 705.168564 s | 788.037110 s | +11.752%; diagnostic passed |
| Artifact records | 1,531 | 1,531 | equal |
| Source records | 104 | 104 | equal |

The candidate accounted for 56 top-level inputs, 104 source identities and 80
logical documents. Terminal outcomes remained 26 `complete` and 78
`review_required`; every accepted document passed zero-silent-loss accounting.

Representation counts remained exact:

| Representation | Count |
| --- | ---: |
| Private normalized source payload | 162 |
| Private normalized source unit | 934 |
| Normalized table projection | 259 |
| Private normalized table slice | 6 |
| Private normalized text slice | 49 |

All deterministic artifact payload digests, representation digests and record
contract digests match the exact pre-goal store. Raw serialized payload bytes
differ by four bytes because measured parser timings and run timestamps are
necessarily different between executions. The oracle excludes exactly
`created_at`, `elapsed_milliseconds_total` and
`layout_elapsed_milliseconds`, plus the absolute calendar expiry while still
requiring the same retention policy/TTL and record-to-policy expiry binding.
Tests fix this exclusion set and prove that any content change remains visible.

## Verification

- Full service suite: `996 passed, 20 skipped`.
- Bounded graph/equivalence/anti-reread tests: `7 passed`.
- Expanded Gate 1, PDF/archive, ArtifactStore, Gate 2 readiness and bundle set:
  `103 passed`.
- Focused Ruff for changed implementation/tests: passed.
- Package façade: passed with only the repository's existing `F401` re-export
  exception.
- Global Ruff: `235` inherited diagnostics; not introduced or expanded by this
  goal and not used as a false green acceptance.
- `compileall`: passed.
- `git diff --check`: passed.
- All three single-file bundles were rebuilt twice with identical SHA-256.

Bundle SHA-256:

- Gate 1: `654c2a54a7ba11c052bd2d92307c8d620746a55866a88c28ecf52550298ad6b4`
- Gate 2 source fact: `3fcfa180d430f25615f35918e11dd07cb23da11f1ce85caaf5e1f09be0930646`
- Gate 2 domain source fact: `9ed753d576e31cdb09fc7c917eee236c646d080807021f0599901f576a8b8a22`

## Privacy and scope

No customer values, private paths, source filenames, ArtifactStore ids or
subprocess output are committed. The repository evidence contains only safe
aggregates and digests. No live stage was mutated. This closure proves the
qualified contour; it does not claim universal input-format support.
