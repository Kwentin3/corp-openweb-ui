# Broker Reports Workflow Goal 5N — Domain Fact Identity Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5n-domain-fact-identity-v1`

Correction family: Gate 2 domain fact identity and answer ownership

Implementation status: PASSED

Live release and reproof: PENDING AFTER MERGE

## Trigger

The native Goal 5M reproof accepted all 39 of 39 domain packages, produced 63
facts, passed all 39 validations and reached complete source coverage with no
source-ref conflicts or fallback. Nevertheless, the run remained
`completed_with_rejections`, so answer-context selection was not executed and
the Gate 3 context manifest remained blocked.

The single downstream conflict was `duplicate_fact_ids`. Two different domain
extractors emitted two semantically different `unknown_source_row` candidates
for the same source scope. Their evidence cardinality matched, but their
semantic payloads did not. The deterministic fact-ID material omitted the
extractor domain, so both candidates received the same ID.

## Root cause

The validator guaranteed ID uniqueness inside one domain package but not
across domain packages for the same source unit. At the fan-in boundary, the
stitcher correctly treated the cross-package collision as unsafe. The answer
context also deduplicated by fact ID without consulting the stitch ownership
map, which would have made an accidental collision choose a presentation by
artifact order.

## Narrow correction

- Added `extractor_domain` to deterministic fact-ID material; broad source-fact
  packages retain an explicit stable namespace.
- Kept fact IDs deterministic across identical replays of the same domain
  package.
- Kept stitch conflict detection unchanged and fail-closed.
- Made answer-context selection resolve every persisted stitch result and
  admit only `owner_fact_id` values with `accepted_fact` or
  `unknown_source_row` ownership.
- Rejects malformed stitch payloads and owned entries without an owner fact ID.
- Preserved backward-compatible answer-context construction for legacy test or
  replay runs that have no stitch-result refs.
- Regenerated all three maintained closed-world Function bundles.

The canonical source-fact schema, model-facing selection contract, Gemini
semantic visual-table contract, Gate 1 representation selection, provider
identities, storage boundaries and Knowledge/RAG policy are unchanged.

## Evidence

- accepted domain packages before correction: 39 of 39;
- rejected domain packages before correction: 0;
- validated source-fact packages: 39 of 39;
- uncovered source refs: 0;
- source-ref conflicts: 0;
- stitch identity conflicts: 1;
- colliding fact candidates: 2;
- distinct semantic variants under the collided ID: 2;
- cross-domain deterministic IDs differ: tested;
- same-domain deterministic ID stability: tested;
- answer context excludes the unowned candidate: tested;
- focused and affected regression tests: 65 passed;
- Ruff: passed;
- Python compile check: passed;
- bundle rebuild reproducibility: 3 of 3 exact;
- `git diff --check`: passed;
- private source-label findings: 0;
- private source-value-literal findings: 0.

SHA-256:

- source-fact validator:
  `7732dd5416e4fbbdc2f351d4de2457110ad79fa1420b76216385498c8bd2ef8d`
- answer-context selection:
  `c7975001e121b44709dfb4f88663867e4a927b5b243e02122293bb7e9c75c3de`
- Gate 1 bundle:
  `8dcbb731c3427ecd83edc0cdf2f1685cbd448e497f53ff3e114eaca464646d11`
- Gate 2 source bundle:
  `9b5b54ccccfe1a4b04b2e4bb497612c33d70d53116aa78cd438552702faa886d`
- Gate 2 domain bundle:
  `74cabe002ad65805b23e516e1e99da2964fd596d6d03be6af77d90109b116709`

## Remaining live question

After atomic release of the exact merged revision, the same native full-domain
workflow must prove terminal `completed`, a ready Gate 3 manifest and a
persisted owner-filtered answer context. This report makes no pre-release live
claim.
