# Broker Reports DOC24 Gate 2 canonical document validation

Date: 2026-08-05  
Scope: research-only; no product activation, parser/cropper change, VLM regeneration, Gate 3, or financial ontology.

## Outcome

- `DOC24_EXPERIMENT = COMPLETED`
- `GATE2_CANONICAL_DOCUMENT = CONFIRMED`
- `LLM_FRIENDLY_PROJECTION = CONFIRMED`
- `MATERIAL_SUFFICIENCY = PRESERVED`
- `ORDERING_FIDELITY = CONFIRMED`
- `GATE2_CONTRACT_DECISION = READY_TO_FORMALIZE`
- `CROP_RESEARCH_POLICY = PAUSE`
- `AUTOMATED_LLM_AUDIT = BLOCKED_EXTERNAL`

## Current handoff truth

The current route remains `Gate1Normalizer -> FullSourceArtifactFactory -> PdfLayoutUnitBuilder -> private source units/table projections -> gate2_handoff_v0 -> Gate 2 source-fact packages`. It has no single interleaved ordered document consumed by Gate 2. The existing compact canonical artifact is table-evidence focused and intentionally excludes line/block inventories; Managed PDF v2 remains an inactive factory surface.

## Candidate and ordering evidence

- 12 non-authoritative candidates: 6 documents x 2 frozen table arms.
- 663/663 unique pages and 34,541/34,541 unique parser lines accounted; 69,130/69,130 arm-specific source atoms; unresolved refs 0.
- 48/48 arm-specific table insertions, representing 24/24 targets; adjacent context 48/48; multi-table errors 0; continuation errors 0; hidden conflicts 0.
- Direct visual review covered 91 pages in 24 contact sheets, including every target/multi-table/continuation/conflict page and 68 stratified remaining pages. Four decorative-only pages were recorded as noncritical visual compression.

## Sufficiency and compression

- Google arm: 22 sufficient, 2 ambiguous, critical loss 0.
- Opus arm: 23 sufficient, 1 ambiguous, critical loss 0.
- Proved duplicate numeric reduction: 95.537757%; duplicate table-line reduction: 95.478723%.
- Unique document-arm projection: 1220828 tokens; reduction from DOC23 target-specific coverage: 79.285498%; reduction from DOC22: 85.550194%.
- Conservative 48-case repeated-document stress count is 6063655 tokens (-2.885575% delta vs DOC23); it is reported but is not the document-level delivery size.

## Verification

Private behavior tests passed 7/7; current architecture/regression tests passed 79/79; final safe-evidence tests passed 4/4; the DOC22-DOC24 evidence chain passed 15/15. The full service suite was attempted twice because the contract makes it conditional on acceptable runtime. The final attempt was externally stopped after 600 seconds: its partial JUnit recorded 1,357 tests, five historical receipt/source-hash failures, and one pytest shutdown error. These are classified in `BROKER_REPORTS_DOC24_TEST_RESULTS.safe.json`; the run is `ABORTED_TIMEOUT`, not a terminal full-suite pass. The external LLM verifier was not started because provider quota was not confirmed; retries, fallbacks, and repairs remain zero.

## Scope stop

DOC24 only permits the next research step `FORMALIZE_GATE2_CANONICAL_DOCUMENT_CONTRACT`. It does not activate a product handoff, replace `gate2_handoff_v0`, start Gate 3, change the cropper/parser, or assign financial semantics.
