# Broker Reports DOC32 PDF canonical round-trip repair

Date: 2026-08-05

Status: `COMPLETED`

## 1. Loss point

The old target image lacked the maintained PDF layout/render dependencies.
FullSource therefore terminally cleared extraction units, and the PDF canonical
adapter emitted only its root container. The first loss was candidate assembly:
the store persisted exactly what it received; manifest and reader did not lose
previously built nodes.

## 2. Why earlier checks missed it

The old validator accepted a non-empty PDF without logical nodes and had no
PDF completeness receipt. DOC30 proved storage lifecycle, hashes and active
pointers, but those checks did not assert consumer-visible PDF nodes.

## 3. Minimum repair

The existing PDF adapter now builds ordered nodes and a counts-only completeness
receipt from existing FullSource units/table projections. Validation fails
closed on non-empty zero-node PDFs or incomplete atom/table accounting. The
closed-world image pins the full parser dependency stack. A tombstone-aware
monotonic version-number fix was added after one failed, non-activating attempt.

## 4. Two trace PDFs

| Cohort index | Pages | Parser lines | Projections | Containers | Nodes | Tables | Components | Reader nodes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 9 | 18 | 939 | 0 (0 ready) | 19 | 35 | 0 | 1 | 35 |
| 12 | 6 | 274 | 14 (9 ready) | 7 | 25 | 9 | 1 | 25 |

Both old candidates had one container and zero nodes. Corrected candidates,
persisted manifests and reader counts match exactly.

## 5. Source-atom accounting

All 27,295 atoms are accounted (27,295
accounted, 0 unresolved). The total comprises
27,164 primary text atoms, 115 primary table atoms and 16 evidence-only visual
atoms. Hidden conflicts, ambiguities and unexplained dropped text/tables are zero.

## 6. PDF node model

The generic model supports `HEADING`, `TEXT`, `LIST`, `TABLE`, `NOTE`,
`PAGE_BREAK`, `CONFLICT` and `AMBIGUITY`. The target cohort emits deterministic
`TEXT`, `PAGE_BREAK` and, where applicable, nine `TABLE` nodes. Ready tables
appear once; duplicate-table text reduction is 100%.

## 7. Isolated round-trip

Both local and final target-image namespaces passed 8/8 publication and a new
process reader: 76 components, non-empty nodes 8/8, table parity 8/8, roots 8/8,
missing chunks 0 and cross-tenant access denied. Frozen DOC24 remains 22/24
Google and 23/24 Opus with zero critical losses and no new provider call.

## 8. Generic LLM-friendly projection

Eight non-empty projections were produced only from reader envelopes. Exact
node/page rendering, 100% source accounting and the DOC24 baseline show zero
critical content loss, unsupported added content or ordering error. The
projector made zero private-evidence/raw-PDF/provider reads and is not Gate 3.

## 9. Eight-document republication

Eight new validated versions were CAS-activated. Active totals are
225 containers, 438 nodes, 9
tables and 76 physical components. Provider, VLM and cropper
calls were zero.

## 10. Old incomplete versions

All eight old versions are preserved unchanged as `SUPERSEDED` forensic
evidence and classified `INCOMPLETE_PDF_CANONICAL_VERSION`. No old payload,
receipt or hash was rewritten.

## 11. Restart, recreation and restore

The existing product service restarted and was recreated with the same image
and named volume. After each operation the reader returned 8/8 PDFs, matched
roots and 76 components with zero missing chunks. SQLite Online Backup passed
integrity/FK checks; isolated restore repeated the same reader/access result.

## 12. Research consumer

`local_pdf_compact_canonical_proof` is migrated to its v2 reader-only output:
8/8 canonical improvements, zero regressions/unresolved comparisons, explicit
flag-off refusal, successful re-enable and zero silent fallback.

## 13. Wave 2 shadow

Six consumers completed three stable 16-document runs: 48/48 `CANONICAL_OK`
per consumer, zero canonical/access regressions, provider requests and product
side effects. The worker returned a terminal PASS receipt before the local SSH
wrapper timed out and was confirmed stopped. Consumers migrated: 0.

## 14. Terminal tests

Focused closure: 98 passed. Extra DOC32 guards: 12 passed. Full suite completed
without timeout: 2,907 passed, 57 failed, 11 errors, 5 skipped. Post-terminal
triage showed 51 order-sensitive failures pass independently, fixed one new PDF
fixture contract mismatch, and left only five frozen-source hash failures plus
11 historical-authority hash errors already accounted by DOC31. Historical
hashes were not rewritten; new unexplained failures are zero.

## 15. Next authority

A separate Wave 2 cutover goal is technically eligible for proposal because
shadow/durability passed. DOC32 does not authorize it. Primary product cutover,
global canonical read, legacy removal and Gate 3 were not performed.
