# Broker Reports Goal 5 — Integrated Actual-Corpus Reproof

Date: 2026-07-21

Implementation commit: `29827e6312eede62802d45d84e86f5fb6df62933`

Branch: `codex/broker-reports-goal5-integrated-reproof-v1`

## Verdict

Goal 5 is accepted for delivery. The authorized corpus was reprocessed twice on the final implementation, every source identity and logical document received an explicit disposition, all 681 generated Gate 2 packages validated without errors or warnings, and the reviewed visual correction produced one additional valid Gate 2 package. Provider executions, review outcomes, private lifecycle, memory/wall bounds, and source ArtifactStore immutability are fully accounted.

No Knowledge/RAG/vector subsystem was used. No corpus payload, private review record, source name, source path, or artifact identifier is recorded in Git. The delegated source review exercised engineering acceptance only; it does not claim customer or independent human sign-off.

## Actual-corpus accounting

| Item | Result |
| --- | ---: |
| Required top-level inputs | 56 |
| Source identities, including promoted archive members | 104 |
| Logical documents | 80 |
| Formats | 2 CSV, 50 PDF, 24 ZIP, 4 HTML text, 24 XML |
| Archive lineage references | 24 |
| Source-fact-ready references | 75 |
| Visual-review references | 5 |
| Terminal source identities | 26 complete, 78 review-required |
| Silent loss | 0 |
| Unexplained terminal states | 0 |

The 24 ZIP containers are now lineage-only records (`archive_lineage` / `not_applicable_lineage_only`) and can never become ordinary source-ready documents. Visual-only scopes are routed to `visual_review_candidate` / `review_required_visual_consumer`, not text source readiness. An early diagnostic counted four no-private-slice items; the final DCP correctly contains five visual-review documents because one additional visual unit had previously been skipped rather than surfaced by that diagnostic.

## Deterministic XML/FNS facts

- 24 typed XML outputs were produced with 351 typed facts.
- 17 structural variants and 24 paired groups were accounted.
- 180 paired PDF candidates remain preserved for review/recovery rather than being silently promoted.
- Unmatched errors, provider calls, tokens, and provider cost are all zero.
- Neutral XML is not captured by the FNS adapter; unknown FNS-shaped schemas and extensions fail closed.

## Reviewed visual handoff and provider accounting

- The inherited sealed workload contains exactly 18 decisions, 36 provider executions, and 36 matching score samples.
- Every execution is reconciled to its provider, input, prompt, model, terminal status, proposal hash, and score sample.
- Exactly one source-reviewed crop was corrected into a 49-cell canonical table and promoted through `PdfVisualTableReviewFactory` and `Gate2TablePackageFactory`.
- All 17 remaining visual decisions received explicit non-accepted receipts.
- Terminal receipt counts are exactly: 1 usable, 8 review-required, 7 rejected, and 2 unsupported.
- Sealed prior provider calls: 36; new provider calls: 0; unaccounted provider calls: 0.

## Gate 2, lifecycle, and immutability

- Gate 2 actual-corpus validation: 681 of 681 packages valid, zero errors, zero warnings.
- Reviewed visual package validation: one of one valid.
- Private review lifecycle: 37 records persisted; a cleanup probe purged three of three records and left zero payloads.
- The source ArtifactStore remained byte-for-byte invariant: 1,531 records and 1,410 payloads before and after, with aggregate signature `4775a097...` unchanged.
- Safe integrated-proof digest: `36d3625acb593593572a1bfcaa95d0a76cc089fff444aae5acdf2c1fea9b478d`.
- Safe FNS proof digest: `b79f2a1eeda636bdd715ae6e02ee34c7700ac60c1ac724adbb738b6fdd9ad183`.

## Bounded reproof

The second final-code run used the first final-code run as its baseline. All 14 bounded-profile checks passed, including semantic and record-contract equivalence.

- Normalization wall time: 686.282965 seconds.
- End-to-end proof wall time: 824.999425 seconds.
- Peak RSS: 4,121,800,704 bytes, below the 5 GiB bound.
- Integrated review wall time: 9.00789 seconds.

## Acceptance

| Criterion | Result |
| --- | --- |
| `ACTUAL_CORPUS_ACCOUNTING` | `COMPLETE` |
| `ZERO_SILENT_LOSS` | `PASSED` |
| `UNEXPLAINED_TERMINAL_STATES` | `ZERO` |
| `KNOWLEDGE_RAG_VECTOR_USE` | `ZERO` |
| `PROVIDER_CALLS` | `FULLY_ACCOUNTED` |
| `REVIEWED_VISUAL_HANDOFF` | `PASSED` |
| `ARTIFACTSTORE_IMMUTABILITY` | `PASSED` |
| `GATE2_VALIDATION_ERRORS` | `ZERO` |

## Verification

- Focused implementation suite: 74 passed.
- Final bundle suite: 11 passed.
- Complete service suite after final bundle generation: 1,030 passed, 20 skipped, zero failed, with five existing SWIG deprecation warnings.
- Ruff passed on the changed source contour. Repository-wide Ruff is not claimed because unrelated legacy violations remain.
- Python compilation of changed runtime entrypoints and generated bundles passed.
- `git diff --check` passed.
- All generated bundles were rebuilt deterministically.

Bundle SHA-256:

- Gate 1: `F38E2C57570C916362D2104CACA52954DFB379E8F98B1A3CC1C1B2C8CD802F62`
- Gate 2 source-fact: `8629FD8848B886E118F882367DF0B8B273770018C97DBA40B9CBB44D7CA464C4`
- Gate 2 domain: `AF0FC5E8D76E3D4D80DB4D374580CA77BA2DF728DCEDE62FE98D87C621A8FD07`

## Scope boundary

The proof used the authorized local corpus and private review materials without copying them into the repository. It did not mutate live OpenWebUI deployment state or production data. Goal 6 and later-stage runtime behavior were not started or changed before this Goal 5 acceptance became terminal.
