# Broker Reports Workflow Goal 2 — Gate 2 Source Contract Audit

Date: 2026-07-22

Audit branch: `codex/broker-reports-goal2-gate2-source-contract-audit-v1`

Audited source revision: `196a6ac0b5979688d55aeca2daf0ad20d41a341b`

Release identity: `broker-reports-196a6ac0b597`

Status: NOT_CLOSED

## Proven upstream path

The fresh native Broker Reports chat had already completed through server-authoritative private intake, the deployed Action, shared WorkloadAuthority and live Gate 1 Function. Its full Gate 2 handoff was ready, with one source-ready document, ten packageable source units, five accepted semantic visual-table representations and zero handoff blockers.

Goal 5F then restored Gate 2 authorization of the owning Gate 1 workload receipt. Independent release readback passed for the exact Git revision, Function bundles, Action, loader, image, prompts, workload configuration and rollback identity.

## Failed invariant

The deployed Gate 2 source Function was invoked through the native OpenWebUI chat route with an approved strict-JSON model. The server-side workload reached `completed` and cleaned its temporary scope, but the extraction run reached `completed_with_rejections`:

- 10 source packages were processed;
- 20 real provider calls completed: one initial call and one bounded repair call per package;
- all 20 responses used strict `json_schema` mode;
- fallback use was zero;
- all 20 privacy and Gate 3 boundary checks passed;
- all 20 candidates failed deterministic validation;
- validated source-fact artifacts: zero;
- Gate 3 handoff readiness: false.

The validator recorded 126 findings. The dominant families were missing provenance bindings (49), coverage mismatches (40) and missing fields (26). The remaining findings concerned model-produced value/reference alignment and deterministic issue carry-forward. A second model attempt supplied the exact validator code/path findings but did not produce one accepted package.

The client-side request channel closed at its 600-second infrastructure limit while the same server workload remained active. No duplicate run was started. Read-only server inspection recovered the terminal completed workload and terminal extraction receipt.

## Root cause

The canonical source-fact artifact is also used almost directly as the model-facing response contract. It asks the model to reproduce application-known package identities, audit metadata, source and evidence references, coverage accounting, issue propagation, validation placeholders and normalized-value reference arrays alongside the semantic fact decision.

Several exact list-valued invariants are conveyed to the provider only as schema descriptions and are checked later by deterministic code. They therefore remain probabilistic model output even though the application already owns the expected values. The observed failures are concentrated in those system-owned fields, not in JSON parsing, provider transport, privacy enforcement or the semantic visual-table transcription contract.

## Ownership and narrowest corrective slice

- Failed invariant: `APPROVED_GATE2_PROVIDER_OUTPUT -> VALIDATED_SOURCE_FACTS`.
- Measured evidence: 10 packages, 20 strict provider calls, 20 rejected validations, zero validated source facts.
- Owning component: Gate 2 source-fact model-facing response contract and deterministic candidate materialization boundary.
- Blocker type: excessive model-facing contract and native workflow integration.
- Narrowest corrective slice: keep the canonical persisted source-fact contract and validator, but introduce a bounded provider response projection containing only semantic choices the model must make. Deterministic code must materialize application-owned scope, audit, coverage scaffold, issue carry-forward, validation placeholders and derivation metadata before canonical validation and persistence.

The Gemini-master semantic visual-table JSON, its prompt, crop extraction, provider selection, private intake, WorkloadAuthority ownership, ArtifactStore lifecycle and Knowledge/RAG policy do not need changes.

## Acceptance disposition

- NATIVE_OPENWEBUI_GATE2_SOURCE_ROUTE: PASSED
- APPROVED_STRICT_MODEL: PASSED
- GATE2_WORKLOAD_TERMINAL_STATE: COMPLETED
- GATE2_EXTRACTION_TERMINAL_STATUS: COMPLETED_WITH_REJECTIONS
- SOURCE_PACKAGES: 10
- STRICT_PROVIDER_CALLS: 20
- FALLBACK_CALLS: ZERO
- VALIDATED_SOURCE_FACTS: ZERO
- PRIVACY_AND_BOUNDARY_CHECKS: 20_OF_20_PASSED
- KNOWLEDGE_RAG_VECTOR_DELTAS: ZERO
- CUSTOMER LABELS OR VALUES IN GIT: ZERO

This report is audit-only and contains no runtime change. Goal 2 remains NOT_CLOSED pending a separate corrective slice and a fresh native Gate 2 proof.
