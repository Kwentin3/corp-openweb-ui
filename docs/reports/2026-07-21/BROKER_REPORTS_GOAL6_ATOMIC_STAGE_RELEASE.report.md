# Broker Reports Goal 6 — Atomic Stage Release

Date: 2026-07-21

Implementation commit: `efc2cd3558add284a1f2fbe182dd850da35a2e98`

Branch: `codex/broker-reports-goal6-atomic-stage-release-v1`

## Verdict

Goal 6 is accepted for delivery. The maintained private-intake Action, all three Broker Reports Functions, twelve managed prompts, loader, dependency, image, provider policy, VLM/review valves, and workload configuration are exact against one repository-derived release manifest. The Function rows were updated in one SQLite transaction while OpenWebUI was stopped, followed by health verification, exact rollback rehearsal, candidate restoration, and an independent live readback.

The stage remains on the previously accepted pinned image. VLM execution is configured with bounded inputs but is disabled by default, and visual auto-publication is disabled. The synthetic private-intake smoke passed all 29 checks and left file, document, Knowledge, ArtifactStore, and vector counters unchanged. No customer document was used.

## Release identity

| Object | Accepted identity |
| --- | --- |
| Source revision | `efc2cd3558add284a1f2fbe182dd850da35a2e98` |
| Release ID | `broker-reports-efc2cd3558ad` |
| Manifest SHA-256 | `b670c1f4b68604c9c33d6650741b5f1fde33de9da09db688871f57a7c401511e` |
| Gate 1 Function | `f38e2c57570c916362d2104caca52954dfb379e8f98b1a3cc1c1b2c8cd802f62` |
| Gate 2 source-fact Function | `8629fd8848b886e118f882367df0b8b273770018c97dba40b9cbb44d7ca464c4` |
| Gate 2 domain Function | `af0fc5e8d76e3d4d80db4d374580ca77ba2df728dcede62fe98d87c621a8fd07` |
| Private-intake Action | `874a07129aa626e61807095b19e531972395934ce1a9aad72d378a3104530ae4` |
| Loader | `28c5eadf6839d9aac5db4f125c31bda5ca6f08d9ce82723c832dd319126703b2` |

All three Functions are active, non-global pipes and carry the accepted revision, bundle hash, and manifest identity in their release metadata. The Action is active, non-global, and exact. All twelve managed prompts are active and exact in command, version, metadata, content, and SHA-256.

## Runtime and policy

- Configured image: `corp-openwebui/openwebui:v0.9.6-native-web-stt-broker-intake-v2-8e6a71f`.
- Image ID: `sha256:c862956b5a88f490de3a13829cb4176ce9a2e3fb3621ebf0198b059be65f8e83`.
- Image revision: `8e6a71f13cf4f9cec0e5be191fac924548050e48`.
- Private-intake contract: `server-authoritative-v2`.
- Container state: running, restart count zero after terminal verification.
- Structural dependency: PyMuPDF `1.26.5`, exact.
- Gate 1 VLM and table intake: disabled by default; candidate, token, output, timeout, page, and raster bounds are present and exact.
- Visual auto-publication: disabled; review and seal markers remain required.
- Gate 2 candidate binding: disabled by default.
- Workload authority: one shared store/configuration, Gate 1 concurrency one and Gate 2 maximum concurrency two; zero nonterminal jobs and zero owned temporary entries at acceptance.

Configured visual model IDs are `models/gemini-3.5-flash` and `gpt-5.4-mini-2026-03-17` under `pdf_dual_vlm_provider_selection_v1`; this does not enable VLM execution. Approved Gate 2 profiles remain OpenAI (`gpt-5.6-luna`, `gpt-5.6-sol`), Anthropic (`claude-haiku-4-5-20251001`), and Google (`models/gemini-3.1-flash-lite`, `models/gemini-3.5-flash`). DeepSeek, ZAI, and Alibaba profiles remain explicitly unsupported.

## Atomic apply and rollback proof

The accepted apply completed in 163.3 seconds. The release driver validated local contracts before transfer, used a restricted release staging directory, stopped OpenWebUI, replaced all three Function rows inside one `BEGIN IMMEDIATE` transaction, restarted the unchanged pinned image, and removed release staging. The terminal receipt records three successful health checks: candidate apply, restored previous state, and restored candidate state.

Rollback rehearsal compared full Function-row snapshots, not only content hashes. Both restoration directions passed exactly:

- immediate rollback artifact: `2f412bf402a1efdec74c723738a9792f0f7bdf24a970f911890a43775f65c663`;
- pre-Goal6 recovery artifact: `3ec986b6d2256a591202769f9f184b6dbc2c4243bc4b21c3919b52b3b829cff8`.

The distinction is deliberate. Because the earlier transport-interrupted remote process later completed the superseded candidate write, the final release's immediate previous rows already contain the same Function bytes as the accepted candidate. The separately retained pre-Goal6 artifact contains the original Function hashes (`9b3895…`, `168a30…`, and `eb1a98…`) and is the recovery point for the state before Goal 6. Both directories are mode `0700`; both artifacts are mode `0600`.

## Safe stage smoke and data invariants

The maintained synthetic private-intake smoke passed all 29 checks. It covered server-authoritative acceptance, client-override denial, generic/native upload rejection, idempotency, Action visibility, private storage, and cleanup. It used synthetic fixtures only and did not use customer documents.

Before and after cleanup:

| Counter | Before | After |
| --- | ---: | ---: |
| ArtifactStore records | 13,301 | 13,301 |
| File rows | 261 | 261 |
| Document rows | 0 | 0 |
| Knowledge rows | 0 | 0 |
| Vector collections | 146 | 146 |
| Vector directories | 146 | 146 |
| Vector files | 595 | 595 |
| Vector bytes | 309,808,908 | 309,808,908 |

All source rows, storage objects, and vector references created by the smoke were absent after cleanup. Knowledge/RAG/vector deltas are zero.

## Interrupted-attempt disclosure

The first apply launcher was mistakenly given a one-second local timeout. Its SSH transport was terminated after the host had stopped OpenWebUI. Immediate inspection found the old Function rows intact and no database transaction in progress; the exact same pinned image was restarted and health-checked. The remote process subsequently survived the local transport loss and completed an atomic write for a superseded source revision, but its receipt was lost. That attempt was rejected from acceptance.

The driver was then hardened to handle `SIGTERM`/`SIGHUP`, restart the prior container when interrupted before the transaction, compare complete rows during rollback, and require a terminal receipt. The accepted revision was preflighted and applied again from scratch, with terminal rollback proof and two independent readbacks. The incident caused no mixed Function state, image drift, Knowledge/RAG/vector change, or retained staging entry.

## Acceptance

| Criterion | Result |
| --- | --- |
| `STAGE_RELEASE` | `ATOMIC` |
| `MIXED_RUNTIME` | `ZERO` |
| `REPOSITORY_LIVE_PARITY` | `EXACT` |
| `PRIVATE_INTAKE` | `PASSED` |
| `KNOWLEDGE_RAG_VECTOR_DELTAS` | `ZERO` |
| `VLM_BOUNDED_INPUT` | `PASSED` |
| `VISUAL_AUTO_PUBLICATION` | `DISABLED` |
| `ROLLBACK` | `PROVEN` |
| `STAGE_CLEANUP` | `PASSED` |

## Verification

- Atomic release-focused hardening suite: 9 passed.
- Goal 6 focused release/private-intake/workload/review suite: 84 passed.
- Complete service suite on the final implementation: 1,039 passed, 20 skipped, zero failed, with five SWIG deprecation warnings.
- Independent atomic live verifier: passed after release and passed again after the private-intake smoke.
- Stage-wide delivery verifier: passed for all Functions, prompts, providers, factory boundaries, dependencies, and default-off valves.
- Ruff passed on the changed Python contour.
- Python compilation of changed runtime entrypoints passed.
- `git diff --check` passed.

## Scope boundary

This release changed the maintained Broker Reports Function rows and their release metadata only. It retained the accepted image, Action, prompts, loader, and dependency exactly. It did not enable VLM, publish visual output automatically, mutate Knowledge/RAG/vector state, or use customer documents. Externally blocked Sber validation remains gated and is not claimed by Goal 6.
