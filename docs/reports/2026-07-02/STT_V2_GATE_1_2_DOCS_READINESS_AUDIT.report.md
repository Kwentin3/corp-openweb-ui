# STT v2 Gate 1-2 Docs Readiness Audit

Date: 2026-07-02.

Status: analytical audit report.

Scope: readiness audit of the STT v2 Gate 1-2 engineering documentation package.

Non-code note: this audit did not implement Gate 1-2 and did not change code,
runtime config, compose, tests, OpenWebUI Action or loader.

## 1. Executive Summary

Verdict: **GO with minor doc fixes**.

The engineering documentation package is ready enough to hand an autonomous
implementation agent a Gate 1-2 goal, provided the goal explicitly points the
agent to the Gate 1-2 goal, contracts and acceptance matrix rather than treating
the full STT v2 blueprint as an immediate implementation list.

The package is strong in the important areas:

- all declared documents exist;
- Gate 1-2 scope is bounded;
- DOCX, prompt catalog, quick actions, auto-run post-processing and chunking are
  explicitly out of scope;
- `TranscriptResultV1`, `ArtifactScopeV1`, `ArtifactRefV1`,
  `ArtifactRecordV1`, minimal `ArtifactChainV1`, retention and transcript store
  contracts are present;
- acceptance matrix has concrete proof rows;
- backward compatibility and no-leak requirements are explicit;
- proof report template requires commands, config, test output and final
  verdict.

Minor fixes recommended before implementation goal:

1. Add a short explicit `ArtifactStoreAdapter` interface snippet to
   `STT_V2_ARTIFACT_CONTRACTS.md`; it currently appears in the blueprint but not
   in the Gate 1-2 artifact contract document.
2. In `STT_V2_GATE_1_2_ENV_CONTRACT.md`, mark proposed `STT_V2_*` env names as
   final-to-confirm against existing `STAGE2_STT_*` names before code changes.
3. In the implementation goal prompt, instruct the agent to use
   `STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md` as the closure authority.

These are documentation tightening items, not blockers.

## 2. Documents Inspected

All requested documents exist.

| Document | Exists | Audit note |
| --- | --- | --- |
| `docs/stage2/goals/STT_V2_GATE_1_2_GOAL.md` | yes | Strong top-level goal, scope and Done/Not Done contract. |
| `docs/stage2/contracts/STT_V2_ARTIFACT_CONTRACTS.md` | yes | Good MVP contract set; minor gap: no explicit `ArtifactStoreAdapter` snippet. |
| `docs/stage2/contracts/STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` | yes | Good storage, retention, refs-first and safety contract. |
| `docs/stage2/contracts/STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md` | yes | Clear regression/compatibility guardrail. |
| `docs/stage2/config/STT_V2_GATE_1_2_ENV_CONTRACT.md` | yes | Plausible runtime knobs; env names should be reconciled with existing Stage 2 naming before code. |
| `docs/stage2/acceptance/STT_V2_DIARIZATION_PROOF_CONTRACT.md` | yes | Good Gate 1 proof contract. |
| `docs/stage2/acceptance/STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md` | yes | Good proof matrix; rows cover happy path and failure/security obligations. |
| `docs/stage2/acceptance/STT_V2_GATE_1_2_PROOF_REPORT_TEMPLATE.md` | yes | Good final proof shape. |
| `docs/stage2/implementation/STT_V2_GATE_1_2_IMPLEMENTATION_BOUNDARY.md` | yes | Clear allowed/forbidden file and feature boundaries. |
| `docs/stage2/context/STT_V2_GATE_1_2_ENGINEERING_DOCS_PLAN.md` | yes | Planning source matches materialized package. |
| `docs/stage2/blueprints/STT_V2_TRANSCRIPT_POSTPROCESSING.blueprint.md` | yes | Full epic blueprint; contains future Gates 3-8 by design. Use through Gate 1-2 documents. |

Completeness verdict: **complete with minor tightening gaps**.

## 3. Scope Containment Verdict

Verdict: **pass**.

Strong containment evidence:

- `STT_V2_GATE_1_2_GOAL.md` lists DOCX, prompt catalog, quick actions,
  auto-run post-processing, chunking, CRM/task tracker, Meetings app, transcript
  history UI and OpenWebUI core patch as non-goals.
- `STT_V2_GATE_1_2_IMPLEMENTATION_BOUNDARY.md` repeats these as forbidden
  areas.
- `STT_V2_ARTIFACT_CONTRACTS.md` states future prompt/DOCX contracts are not
  required for Gate 1-2.
- `STT_V2_DIARIZATION_PROOF_CONTRACT.md` explicitly excludes prompt catalog,
  quick actions, post-processing, DOCX and chunking.
- The acceptance matrix includes a scope-creep row: no DOCX/prompt/quick-action
  implementation.

Potential ambiguity:

- The full blueprint intentionally includes Gates 3-8 and sections on prompt
  catalog, quick actions, long transcript policy and DOCX. This is acceptable
  for the epic blueprint, but an implementation agent must not treat the
  blueprint alone as the implementation goal.

Required mitigation:

- The implementation goal must explicitly say: the Gate 1-2 goal document and
  acceptance matrix override future sections of the full blueprint for this
  slice.

## 4. Contract Consistency Verdict

Verdict: **mostly pass, one minor gap**.

### TranscriptResultV1

Pass.

The artifact contract preserves:

- text;
- segments;
- words;
- timestamps;
- speaker labels;
- warnings;
- safe provider metadata;
- transcript hash;
- optional diagnostic provider ref.

It also states product flow must work without
`internal_provider_response_ref`.

### ArtifactScopeV1

Pass.

The package consistently treats `ArtifactScopeV1` as context binding, not:

- ACL;
- ownership proof;
- security boundary;
- tenant/multitenant model.

`tenant_id` remains nullable optional/future. No document makes it mandatory.

### ArtifactRefV1

Pass.

Refs are required to be opaque, unguessable and insufficient for access by
themselves.

### ArtifactRecordV1

Pass.

The contract separates record payload, refs, metadata, warnings, retention class
and parent refs. It forbids secrets and raw provider payload in product records.

### ArtifactChainV1

Pass.

The package says `ArtifactChainV1` is lineage-only and not:

- workflow engine;
- execution orchestrator;
- job status replacement;
- access-check replacement.

### ArtifactRetentionPolicyV1

Pass.

Retention defaults and expiry behavior are defined. Expired refs must return
typed refusal and be non-retrievable.

### TranscriptProjectionV1

Pass.

Projection is optional for Gate 1 unless used for speaker-labeled proof. It is
derived only from normalized `TranscriptResultV1`.

### TranscriptStoreAdapter

Pass.

The contract correctly models it as a facade over `ArtifactStoreAdapter`.

### ArtifactStoreAdapter

Minor gap.

The blueprint contains an `ArtifactStoreAdapter` interface, but the Gate 1-2
artifact contract document does not repeat the interface snippet. Because the
implementation agent will use the Gate 1-2 docs as the immediate contract pack,
this should be added to `STT_V2_ARTIFACT_CONTRACTS.md`.

Suggested addition:

```text
put_artifact(record) -> ArtifactRefV1
get_artifact(artifact_ref, user_context) -> ArtifactRecordV1
link_artifacts(from_ref, to_ref, transform) -> ArtifactChainV1
list_chain(root_or_ref, user_context) -> ArtifactChainV1
expire_artifact(artifact_ref, reason)
delete_scope(scope, reason)
```

## 5. Acceptance Matrix Review

Verdict: **pass**.

The matrix covers required happy paths and proof obligations.

Required rows checked:

- capabilities show speaker support: present as `G1-DIA-002`;
- synthetic two-speaker audio returns speaker labels: present as `G1-DIA-006`;
- `TranscriptResultV1.segments[].speaker` populated: present as `G1-DIA-007`;
- `TranscriptResultV1.words[].speaker` checked if provider returns words:
  present as `G1-DIA-008`;
- `transcript_ref` created: present as `G2-ART-001`;
- `TranscriptResultV1` retrievable by `transcript_ref`: present as
  `G2-ART-002`;
- flat `Transcript:` output remains backward-compatible: present as `BC-001`;
- artifact refs are opaque/unguessable: present as `G2-ART-010`;
- SQLite/volume path not browser-accessible: present as `G2-ART-011`;
- expired artifact not retrievable: present as `G2-ART-009`;
- access failure returns typed refusal: covered by `G2-ART-009`, `G2-ART-011`
  and boundary/storage contracts, but could be made more explicit;
- loader-visible refs are not sufficient for access: covered in goal/storage and
  compatibility contracts, not a standalone matrix row;
- product path works without diagnostic raw provider payload: present as
  `G2-ART-013`;
- raw LemonFox JSON absent from chat/action/loader/logs/product artifact rows:
  present as `G1-DIA-010`;
- artifact store failure does not corrupt ordinary OpenWebUI chat: present as
  `BC-002`.

Optional matrix improvements:

Add two explicit rows to reduce reviewer interpretation:

```text
G2-ART-015 | Access failure returns typed refusal | wrong user/context returns artifact_access_denied or artifact_scope_unverified | unit/API test | TBD | | STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md
G2-ART-016 | Loader-visible refs are not sufficient for access | valid-looking client ref without matching server-side context is refused | unit/API test | TBD | | STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md
```

These are optional because the requirement is already covered elsewhere, but
explicit rows would make matrix closure cleaner.

## 6. Implementation Boundary Review

Verdict: **pass**.

Allowed areas are clear:

- `services/stage2-stt/stage2_stt/*` for contracts, config, runtime, provider,
  app, storage and job-store work;
- new artifact/transcript/projection modules if needed;
- focused Gate 1-2 tests;
- Action bridge only for `transcript_ref` and backward-compatible response path.

Forbidden areas are clear:

- DOCX;
- prompt catalog;
- quick actions UI;
- auto-run post-processing;
- chunking;
- OpenWebUI core patch;
- separate transcript history UI;
- Meetings app.

No ambiguity that should block implementation was found.

Minor recommendation:

- In the implementation-goal prompt, repeat that touching
  `stage2_media_transcription_action.py` is allowed only for
  `transcript_ref`/safe warnings/backward compatibility, not for prompt or DOCX
  behavior.

## 7. Runtime / Env Review

Verdict: **mostly pass with one non-blocking naming question**.

Pass:

- diarization flag is explicit:
  `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true`;
- `speaker_labels=true` and `response_format=verbose_json` are explicit;
- missing speaker-label flag defaults to false;
- artifact-store missing config must not create fake durability;
- no silent in-memory fallback for Gate 2 Done;
- retention defaults are explicit;
- diagnostic raw provider payload disabled by default;
- prepared audio TTL is explicit;
- capability endpoint expectations are UI-safe.

Non-blocking naming question:

- The env contract proposes new `STT_V2_*` names while the existing STT env
  contract/code use `STAGE2_STT_*` and `STAGE2_LEMONFOX_*`.

This is acceptable because the document says these are recommended variable
names, but implementation should reconcile names before code changes.

Specific names to verify before implementation:

- `STT_V2_ARTIFACT_STORE_MODE`
- `STT_V2_ARTIFACT_STORE_PATH`
- `STT_V2_ARTIFACT_PAYLOAD_DIR`
- `STT_V2_TRANSCRIPT_TTL_DAYS`
- `STT_V2_PREPARED_AUDIO_TTL_HOURS`
- `STT_V2_DIAGNOSTIC_PROVIDER_PAYLOAD_ENABLED`

Recommendation:

- either keep `STT_V2_*` as the new namespace and document it as final;
- or align with existing `STAGE2_STT_*` naming before code.

Not a blocker for issuing the implementation goal.

## 8. Security / No-leak Review

Verdict: **pass**.

The package requires proof for:

- no raw LemonFox JSON in chat;
- no raw LemonFox JSON in Action output;
- no raw LemonFox JSON in loader/browser state;
- no raw LemonFox JSON in ordinary logs;
- no raw LemonFox JSON in product artifact rows;
- no API keys/tokens/internal URLs in artifact payloads;
- SQLite/volume store not browser-accessible;
- opaque/unguessable artifact refs;
- fail-closed access behavior;
- diagnostic raw provider payload disabled by default.

No document was found that intentionally allows raw provider payload into product
paths. Diagnostic provider payload is consistently marked disabled or
diagnostic-only.

Minor risk:

- The proof template asks for scans but does not define exact log source names.
  This is acceptable; the implementation agent can resolve it during Gate 1-2
  because log topology is runtime-specific.

## 9. Backward Compatibility Review

Verdict: **pass**.

The package protects:

- existing flat `Transcript:` output;
- chat-safe Action response;
- base STT behavior if artifact prerequisites are unavailable;
- typed safe errors;
- no OpenWebUI core patch;
- loader-visible refs not trusted.

The compatibility contract correctly states artifact-store failure should not
corrupt ordinary chat.

Minor implementation caution:

- If Action return shape is changed to carry `transcript_ref`, tests must prove
  the visible chat text remains compatible.

## 10. Proof Report Template Review

Verdict: **pass**.

The template requires:

- changed files;
- config used;
- test commands;
- test outputs/short results;
- diarization proof;
- synthetic audio proof;
- sidecar capabilities proof;
- artifact-store proof;
- `transcript_ref` proof;
- no-leak proof;
- backward compatibility proof;
- limitations;
- open questions;
- final verdict.

Optional additions:

```text
- include git diff scope summary;
- include acceptance matrix row status table inline or as an attached copy;
- include exact log source list used for no-leak scan.
```

These would improve review ergonomics but are not blockers.

## 11. Open Questions Classification

### A. Blockers Before Implementation Goal

None.

No open question prevents issuing an implementation goal if the goal references
the current document package and requires the acceptance matrix to close.

### B. Implementation Agent Can Resolve During Gate 1-2

- Exact OpenWebUI user/chat/file identifiers available to Action, loader and
  sidecar in the target runtime.
- Final env variable naming for artifact-store config.
- Exact synthetic two-speaker fixture generation method or fixture path.
- Exact runtime command proving SQLite/volume is not browser-accessible.
- Exact log sources for no raw provider leak proof.
- Whether sidecar restart durability is proven in Gate 2 or explicitly accepted
  as a controlled limitation for first pass.

These are implementation/proof decisions, not architecture blockers.

### C. Future Gates / Not Relevant Now

- OpenWebUI prompt catalog seed and access proof.
- Quick action UX and auto-run execution.
- Long transcript chunking.
- DOCX endpoint/file API path.
- Post-processing result contracts.
- Separate transcript history UI, which is explicitly a non-goal.

## 12. Checklist With Pass / Fail

```text
[x] Все заявленные документы существуют.
[x] Goal ограничен Gate 1-2.
[x] DOCX явно out of scope.
[x] Prompt catalog / quick actions / auto-run post-processing явно out of scope.
[x] OpenWebUI core patch запрещён без ADR.
[x] `TranscriptResultV1` сохраняется как canonical product artifact.
[x] `ArtifactScopeV1` не является ACL/security/tenant model.
[x] `ArtifactChainV1` lineage-only, not workflow engine.
[x] ArtifactStore internal technical store, not user-facing transcript history.
[x] `transcript_ref` обязателен для Gate 2.
[x] Artifact refs opaque/unguessable.
[x] SQLite/volume not browser-accessible.
[x] Retention/expiry defined.
[x] Raw LemonFox JSON not product artifact.
[x] Product path works without diagnostic raw provider payload.
[x] Synthetic two-speaker proof required.
[x] `verbose_json` + `speaker_labels=true` required for LemonFox diarization.
[x] Normalized speaker fields must be inspected.
[x] Flat `Transcript:` output remains backward-compatible.
[x] Artifact-store failure does not corrupt ordinary chat.
[x] Acceptance matrix has proof rows, not only narrative criteria.
[x] Proof report template requires commands/config/test outputs.
[x] Open questions are classified by blocker/non-blocker/future.
[x] Final verdict is explicit.
```

Checklist verdict: **pass**.

## 13. Required Fixes

Required before implementation goal: **none**.

Required before or during first implementation PR:

1. Decide final env variable naming for artifact-store settings:
   `STT_V2_*` vs `STAGE2_STT_*`.
2. Add or keep implementation proof that Action-visible text remains compatible
   if `transcript_ref` is added.

## 14. Optional Improvements

1. Add explicit `ArtifactStoreAdapter` snippet to
   `STT_V2_ARTIFACT_CONTRACTS.md`.
2. Add acceptance matrix rows:
   - access failure returns typed refusal;
   - loader-visible refs are not sufficient for access.
3. Add exact log source list to proof report template.
4. Add a short implementation-goal preamble saying the Gate 1-2 goal/matrix
   override future blueprint sections for this slice.
5. In the env contract, mark proposed `STT_V2_*` names as either final or
   explicitly pending naming reconciliation.

## 15. Final Readiness Verdict

Final verdict: **GO with minor doc fixes**.

Main reasons:

1. All requested documents exist and form a coherent chain:
   Goal -> contracts -> env/runtime -> acceptance matrix -> implementation
   boundary -> proof report.
2. Scope containment is strong; future STT v2 surfaces are repeatedly out of
   Gate 1-2 scope.
3. Contract consistency is good; `ArtifactScopeV1`, `ArtifactChainV1`,
   ArtifactStore and raw provider payload policies are disciplined.
4. Acceptance matrix is concrete and includes security, failure and compatibility
   proof rows.
5. Implementation boundary is clear enough for an autonomous agent.
6. Runtime/env contract is feasible, with only a naming reconciliation question.
7. Backward compatibility and no-leak proof obligations are explicit.

Mandatory fixes before issuing implementation-goal:

- none.

Recommended minor fixes:

- add `ArtifactStoreAdapter` snippet to the artifact contract document;
- add two explicit matrix rows for typed access refusal and loader-visible refs;
- clarify final env variable naming.

What should not block implementation:

- exact synthetic fixture generation method;
- exact log source list;
- exact OpenWebUI identifier availability;
- sidecar restart proof depth, as long as the implementation goal requires the
  acceptance matrix to record proof or controlled limitation.

The package is fit to issue a bounded autonomous Gate 1-2 implementation goal.
