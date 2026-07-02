# STT v2 Gate 1-2 Proof Report Template

Status: report template.

Date: 2026-07-02.

Scope: template for the final implementation/proof report that closes
`STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md`.

## 1. Summary

```text
Verdict: Ready | Not Ready | Blocked
Gate 1 verdict: Ready | Not Ready | Blocked
Gate 2 verdict: Ready | Not Ready | Blocked
Implementation branch/commit:
Runtime target:
```

## 2. Changed Files

List all changed files grouped by:

- contracts/models;
- sidecar routes;
- provider adapter;
- storage;
- Action bridge;
- tests;
- docs/config.

Confirm:

- no OpenWebUI core patch;
- no DOCX implementation;
- no prompt catalog implementation;
- no quick actions/post-processing implementation;
- no chunking implementation.

## 3. Config Used

Include safe effective config:

```text
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=
STAGE2_STT_ARTIFACT_STORE_MODE=
STAGE2_STT_TRANSCRIPT_TTL_DAYS=
STAGE2_STT_PREPARED_AUDIO_TTL_HOURS=
STAGE2_STT_DIAGNOSTIC_PROVIDER_PAYLOAD_ENABLED=
```

Do not include secrets, API keys, raw env dumps or provider headers.

## 4. Test Commands

Record exact commands:

```text
<command>
<exit code>
<short result>
```

Include targeted tests and any smoke/runtime proof commands.

## 5. Gate 1 Diarization Proof

Record:

- runtime flag proof;
- capabilities proof;
- provider request parameter proof;
- synthetic two-speaker fixture metadata;
- normalized `TranscriptResultV1` speaker fields;
- word-speaker proof if provider returns word speakers;
- no raw provider leak proof.

## 6. Gate 2 Artifact-store Proof

Record:

- `transcript_ref` example, redacted if needed;
- artifact record proof;
- transcript retrieval proof;
- `ArtifactScopeV1` proof;
- artifact lineage proof;
- retention/expiry proof;
- storage path negative browser-access proof;
- opaque/unguessable ref proof;
- fail-closed access proof.

## 7. Backward Compatibility Proof

Record:

- flat `Transcript:` output proof;
- provider error behavior proof;
- artifact-store failure behavior proof;
- base chat availability statement;
- no OpenWebUI core patch proof.

## 8. No-secrets / No Raw Provider Leak Proof

Record scans for:

- raw LemonFox JSON markers;
- provider headers;
- API keys;
- OpenWebUI auth tokens;
- signed internal URLs;
- transcript payload in ordinary logs.

## 9. Acceptance Matrix Closure

Copy or link every row from:

```text
docs/stage2/acceptance/STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md
```

Every row must be:

```text
Pass | Fail | Blocked
```

No row may remain `TBD`.

## 10. Known Limitations

List limitations that do not invalidate Gate 1-2, for example:

- no prompt catalog;
- no quick actions;
- no DOCX;
- no chunking;
- no object storage URL provider path;
- no separate transcript history UI.

## 11. Open Questions

List open questions with owner and next action.

## 12. Final Verdict

```text
Gate 1:
Gate 2:
Overall:
Rationale:
Next recommended gate:
```
