# Broker Reports Workflow Goal 5B — Native Gate 1 Idempotency Live Reproof

Date: 2026-07-22

Audit branch: `codex/broker-reports-goal5b-live-reproof-audit-v1`

Audited source revision: `39999d689ea0268f24d484bb38f874d6f6497986`

Release identity: `broker-reports-39999d689ea0`

Status: NOT_CLOSED

## Release verification

The Goal 5B correction was merged through PR #25 and atomically released from approved `main`. Independent live readback passed for all three Function bundles, the private-intake Action, loader, image, 12 managed prompts, workload configuration, semantic contract identity and forbidden Knowledge/RAG/vector policy. The release staging area was empty, workload state was quiescent before the proof, and rollback identity SHA-256 was `efd759d53dad264e9428184beeb02bcffb675acba2a17c14e8e9f60aff1df59b`.

## Native reproof result

The reproof used the real server-authoritative private-intake route, deployed Action and native `/api/chat/completions` task path with the sealed-source PDF. It created one native OpenWebUI task and reached normal terminal chat content. Knowledge, RAG and vector deltas remained zero.

The idempotency invariant nevertheless failed:

- Gate 1 workload jobs: 2, both terminal `completed`;
- completed workload transitions: 2;
- domain context packets: 2;
- newly persisted artifacts: 40, comprising two complete 20-artifact sets;
- normalization run identities: 1 deterministic identity;
- idempotency keys: present on both jobs but distinct.

The two jobs had identical trusted user, case, chat and source identities. Their only workload-scope difference was `workspace_model_id`: the first native Function invocation supplied no workspace-model context, while the second supplied the deployed Gate 1 model identity. Because the first correction included this invocation-volatile optional field in the key, the two submissions did not collide.

No package was selected arbitrarily. Goal 2 remains NOT_CLOSED because two equally terminal DCPs exist for one native source scope.

## Failed invariant and ownership

- Failed invariant: `DUPLICATE_GATE1_JOBS_PER_NATIVE_SOURCE_SCOPE = ONE`.
- Measured evidence: one native task produced two completed jobs, two completed transitions, two DCPs and 40 artifacts.
- Owning component: Gate 1 Function workload identity derivation at the `WorkloadAuthority` submission boundary.
- Blocker type: native OpenWebUI invocation-context variation, not document parsing, semantic JSON, VLM, provider or ArtifactStore failure.
- Narrowest corrective slice: bind Gate 1 workload identity to a stable Function-owned workspace scope while retaining server-attested user and case/chat scope plus source identity; prove that missing-versus-present invocation model metadata maps to one job, while actual user/chat/source substitution remains rejected.

## Privacy and boundary disposition

- expected control values exposed to runtime: zero;
- private reference exposed to runtime: zero;
- customer labels or values in Git evidence: zero;
- answering-model PDF or crop access: zero;
- Knowledge/RAG/vector deltas: zero;
- semantic JSON or Gemini prompt changes: zero.

This report is audit-only. It contains no runtime correction. A new branch from the accepted `main` is required for the narrow identity-normalization slice.
