# Broker Reports Workflow Goal 5A — Context Selection Correction

Date: 2026-07-22  
Branch: `codex/broker-reports-workflow-goal5-context-selection-v1`  
Correction family: context representation selection and answer-context assembly  
Implementation status: PASSED  
Live three-metric reproof: PENDING AFTER MERGE

## Trigger

Goal 1 audit PR #22 established that the deployed Gate 1/Gate 2 contour preserved the semantic visual table and the retained source, but produced no maintained final answer-context payload. Consequently it could not prove one interpretation-bearing representation per source scope or zero duplicate financial-fact presentation to the answering model.

## Narrow correction

The correction adds `AnswerContextSelectionFactory` after a completed Gate 2 domain run. It does not change the Gemini semantic JSON contract, VLM prompt, provider choice, crop extraction, private-intake route, Gate ownership, Knowledge/RAG policy or local OCR policy.

The factory builds two persisted artifacts:

- a private `broker_reports_answer_context_v1` payload for the answering boundary;
- a safe `broker_reports_answer_context_selection_receipt_v1` containing only counts, hashes, refs and terminal flags.

Existing identities are reused. An evidence group is derived deterministically from the existing document, source-unit and table-projection identities. No parallel identity model was introduced.

For a semantic visual-table scope:

- the validated semantic transcription is the only `interpretation_bearing` representation;
- retained full-source and normalized-source artifacts are `provenance_only` and contribute no financial content to the answer payload;
- Gate 2 packages and validated facts derived from that table are also `provenance_only` in the final context, preventing a second presentation of the same values;
- source document, page and section identities remain available for citation and resolver-controlled audit.

For a non-semantic scope, validated Gate 2 facts are compacted into one interpretation-bearing representation per source unit; retained source evidence remains provenance-only.

The validator fails closed if a group has zero or more than one interpretation-bearing representation, if semantic content is not the selected representation, if provenance-only content carries financial payload, or if PDF/crop bytes, raw provider output, sealed expected values, Knowledge/RAG context or embeddings appear.

## Runtime and release wiring

`Gate2DomainSourceFactRuntimeFactory` invokes the selector only after a terminal `completed` run. Planned answer-context and receipt refs are written into the immutable terminal run before persistence and verified against the factory result. Blocked runs publish neither artifact.

The production valve `answer_context_selection_enabled` defaults to `true`, and the atomic release contract pins it to `true`. Deterministic Gate 2 bundles were regenerated:

- source bundle SHA-256: `79ea447de901513684d0159063a8f46b4b2e78d74adc06690ae44c1e27aa7341`;
- domain bundle SHA-256: `cb8f6fb9b20e2e73f50747402ddb04491a235b1864e1cf31703422735d47a39e`;
- selector source SHA-256: `3fa0e4839fffe541cc178f13515a94e4169598568789bb9b772e27e04228e31a`.

The bundled module is loaded from the generated closed-world package. No workspace-only import, filesystem path bridge, new dependency or environment variable was added.

## Verification

Focused semantic proof uses the real Gate 1 normalizer, semantic migration, ArtifactStore, Gate 2 readiness and resolver. Two derived Gate 2 windows were deliberately bound to one semantic projection; the resulting answer context contained one evidence group and exactly one interpretation-bearing semantic table. Provenance records contained refs only, remained resolver-accessible, and a deliberately duplicated interpretation failed validation.

Factory anti-drift proof also runs through the actual Gate 2 domain runtime and verifies that a completed run persists and resolves its answer context and safe receipt.

Terminal local results:

- affected runtime, semantic, bundle, architecture and atomic-release regression: 56 passed;
- artifact lifecycle regression in a fresh process: 8 passed;
- repository privacy guard in a fresh process: 3 passed;
- Ruff on changed production/test sources: passed;
- `git diff --check`: passed.

One earlier mixed pytest invocation loaded the generated closed-world package under the production module name before an introspection-only lifecycle test. That caused test-process module shadowing, not a product failure. The lifecycle suite passed in its required fresh process and the bundle suite independently passed.

## Acceptance disposition

- SOURCE_SCOPE_GROUPING: IMPLEMENTED
- INTERPRETATION_BEARING_REPRESENTATIONS: ONE_PER_SCOPE IN LOCAL FACTORY/RUNTIME PROOF
- PROVENANCE_ONLY_REPRESENTATIONS: NOT COUNTED AS FACTS
- SEMANTIC_DUPLICATE_FACTS_IN_ANSWER_CONTEXT: ZERO IN LOCAL PROOF
- SOURCE_EVIDENCE: PRESERVED AND RESOLVER-CHECKED
- LLM_DEDUPLICATION_GUESSWORK: ZERO BY CONTRACT
- SEMANTIC JSON OR PROMPT CHANGE: ZERO
- PRIVATE CUSTOMER EVIDENCE IN GIT: ZERO

Goal 5A implementation is complete. Goal 1 remains pending only for the mandated live three-control-metric payload inspection after this correction is merged and atomically released from approved `main`.
