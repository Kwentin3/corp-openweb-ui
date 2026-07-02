# STT v2 Gate 1-2 Acceptance Matrix

Status: Gate 1-2 verification matrix.

Date: 2026-07-02.

Scope: acceptance checklist for STT v2 Gate 1-2 implementation.

## 1. Usage

The implementation agent must fill this matrix in the final proof report.

Columns:

```text
ID | Requirement | Expected proof | Test/report artifact | Pass/Fail | Notes | Linked contract
```

`Pass` requires a concrete command, test name, report artifact or inspected
runtime evidence. Unsupported or not-run rows must be `Fail` or `Blocked`, not
left ambiguous.

## 2. Gate 1: Diarization Proof

| ID | Requirement | Expected proof | Test/report artifact | Pass/Fail | Notes | Linked contract |
| --- | --- | --- | --- | --- | --- | --- |
| G1-DIA-001 | Speaker-label flag enabled in test runtime | Effective config shows `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true` without secrets | proof script output / server env probe | Pass | Local proof and PRD-0 server env both have speaker labels enabled; API key status only is reported | `STT_V2_GATE_1_2_ENV_CONTRACT.md` |
| G1-DIA-002 | Capabilities show speaker support | Capabilities response has `supports_speaker_labels=true` | proof script output / server capability probe | Pass | Capability response contains no secrets/paths; server probe returned `supports_speaker_labels=True` | `STT_V2_DIARIZATION_PROOF_CONTRACT.md` |
| G1-DIA-003 | Provider request uses speaker labels | Adapter/request test proves `speaker_labels=true` | `pytest tests/test_lemonfox_adapter.py` | Pass | `test_lemonfox_request_form_enables_speaker_labels_and_verbose_json` | `STT_V2_DIARIZATION_PROOF_CONTRACT.md` |
| G1-DIA-004 | Provider request uses verbose JSON | Adapter/request test proves `response_format=verbose_json` | `pytest tests/test_lemonfox_adapter.py` | Pass | Same request-form test | `STT_V2_DIARIZATION_PROOF_CONTRACT.md` |
| G1-DIA-005 | Synthetic two-speaker fixture exists | Fixture path/generation method, duration, checksum | proof artifact/report | Pass | `docs/reports/2026-07-02/STT_V2_GATE_1_2_PROOF_ARTIFACTS/synthetic-two-speaker.wav` | `STT_V2_DIARIZATION_PROOF_CONTRACT.md` |
| G1-DIA-006 | Synthetic audio returns speaker labels | Transcript contains at least two distinct speaker labels when provider returns them | live integration proof | Pass | `.env` key loaded; synthetic WAV returned `SPEAKER_00` and `SPEAKER_01` | `STT_V2_DIARIZATION_PROOF_CONTRACT.md` |
| G1-DIA-007 | Segment speakers normalized | `TranscriptResultV1.segments[].speaker` populated | `pytest tests/test_lemonfox_adapter.py tests/test_stt_v2_artifact_store.py` | Pass | Normalized provider-shaped payload preserves segment speakers | `STT_V2_ARTIFACT_CONTRACTS.md` |
| G1-DIA-008 | Word speakers normalized when available | `words[].speaker` populated if provider returns word speaker data | `pytest tests/test_lemonfox_adapter.py tests/test_stt_v2_artifact_store.py` | Pass | Word-speaker proof is conditional on provider returning word speakers | `STT_V2_ARTIFACT_CONTRACTS.md` |
| G1-DIA-009 | No invented participant names | Projection/output uses generic provider-normalized labels only | test/report inspection | Pass | Tests preserve generic `speaker_0` / `speaker_1`; no projection names invented | `STT_V2_DIARIZATION_PROOF_CONTRACT.md` |
| G1-DIA-010 | No raw provider leak | Raw LemonFox payload absent from chat/action/loader/logs/product artifacts | test/db/grep proof | Pass | Raw provider marker excluded from normalized result and SQLite product artifacts | `STT_V2_DIARIZATION_PROOF_CONTRACT.md` |

## 3. Gate 2: Artifact Store And Structured Transcript

| ID | Requirement | Expected proof | Test/report artifact | Pass/Fail | Notes | Linked contract |
| --- | --- | --- | --- | --- | --- | --- |
| G2-ART-001 | `transcript_ref` exists | Successful STT response or internal result has opaque transcript ref | `pytest tests/test_job_routes.py` / proof script | Pass | Response returns `art_...` ref when SQLite store enabled | `STT_V2_ARTIFACT_CONTRACTS.md` |
| G2-ART-002 | `TranscriptResultV1` retrievable by ref | `get_transcript(transcript_ref)` returns full normalized result | `pytest tests/test_job_routes.py tests/test_stt_v2_artifact_store.py` | Pass | Safe sidecar path returns structured result | `STT_V2_ARTIFACT_CONTRACTS.md` |
| G2-ART-003 | Structured fields preserved | text, segments, words, timestamps, speakers, warnings remain available | `pytest tests/test_stt_v2_artifact_store.py` | Pass | Segment/word speakers and hash survive store/reload | `STT_V2_ARTIFACT_CONTRACTS.md` |
| G2-ART-004 | Durable artifact record exists | SQLite/volume record exists after successful STT job | proof SQLite artifact | Pass | Proof DB has 4 artifact records | `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` |
| G2-ART-005 | `ArtifactScopeV1` is recoverable | record carries available context identifiers only | `pytest tests/test_job_routes.py tests/test_stt_v2_artifact_store.py` | Pass | Missing tenant allowed; user/chat/message/file stored when available | `STT_V2_ARTIFACT_CONTRACTS.md` |
| G2-ART-006 | Minimal lineage exists | source file ref, prepared audio ref/metadata, STT job and transcript linked | `pytest tests/test_stt_v2_artifact_store.py` / proof DB | Pass | Chain edges: normalize_audio, transcribe, transcribe | `STT_V2_ARTIFACT_CONTRACTS.md` |
| G2-ART-007 | Transcript index exists | `transcript_index` maps ref/hash/chain/artifact | DB/test proof | Pass | Proof DB has 1 transcript_index row | `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` |
| G2-ART-008 | Retention defaults applied | created records have expected `expires_at` / retention class | DB/test proof | Pass | Config defaults enforced; records carry retention classes and expiry | `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` |
| G2-ART-009 | Expired artifact not retrievable | expired ref returns `artifact_expired` or equivalent typed refusal | `pytest tests/test_stt_v2_artifact_store.py` | Pass | `test_expired_transcript_ref_returns_typed_refusal` | `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` |
| G2-ART-010 | Artifact refs opaque/unguessable | tests show no sequential/browser-guessable refs | `pytest tests/test_stt_v2_artifact_store.py` | Pass | 100 generated refs unique, `art_` opaque, non-sequential | `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` |
| G2-ART-011 | SQLite/volume not browser-accessible | HTTP/static negative check | proof report/code review | Pass | No static route serves store path; only internal authenticated transcript endpoint exists | `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` |
| G2-ART-012 | Payloads absent from ordinary logs | log scan shows no transcript/provider payload | grep/proof report | Pass | No logger/print payload path; proof output contains safe refs/counts only | `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` |
| G2-ART-013 | Product path works without diagnostic payload | tests pass with diagnostic provider payload disabled | `pytest` / config test | Pass | Diagnostic provider payload config must remain false | `STT_V2_ARTIFACT_CONTRACTS.md` |
| G2-ART-014 | Product path works without rendered prompt snapshot | transcript storage/proof does not require prompt snapshot | `pytest` / diff scope proof | Pass | Gate 1-2 has no prompt execution | `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` |
| G2-ART-015 | Access failure returns typed refusal | wrong user/context returns `artifact_access_denied` or `artifact_scope_unverified` | `pytest tests/test_job_routes.py tests/test_stt_v2_artifact_store.py` | Pass | Wrong user and missing context both fail closed | `STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md` |
| G2-ART-016 | Loader-visible refs are not sufficient for access | valid-looking client ref without matching server-side context is refused | `pytest tests/test_job_routes.py` / proof script | Pass | Ref-only request returns `artifact_scope_unverified` | `STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md` |
| G2-ART-017 | Post-actions preserve OpenWebUI file identity | quick actions use the same file id that created `transcript_ref`, including prepared upload ids after browser normalization | `pytest tests/test_loader_static.py tests/test_openwebui_action.py` | Pass | Loader binds actions to `preparedFile`; source attachment id is not substituted | `STT_V2_ARTIFACT_CONTRACTS.md` |

## 4. Backward Compatibility

| ID | Requirement | Expected proof | Test/report artifact | Pass/Fail | Notes | Linked contract |
| --- | --- | --- | --- | --- | --- | --- |
| BC-001 | Flat transcript output unchanged | Existing Action returns compatible `Transcript:` text | `pytest tests/test_openwebui_action.py` | Pass | Content still starts with `Transcript:\n\n...`; ref is additive | `STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md` |
| BC-002 | Artifact-store failure does not corrupt chat | forced store failure still returns safe flat output or typed safe error | `pytest tests/test_job_routes.py` | Pass | Disabled store returns no fake ref and warning only | `STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md` |
| BC-003 | Normal chat remains usable | loader/artifact failures do not block base chat | test/proof report | Pass | Artifact retrieval failures are isolated to internal endpoint | `STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md` |
| BC-004 | No OpenWebUI core patch | diff review shows no core patch | git diff proof | Pass | Changes stay under `services/stage2-stt` plus Gate docs/reports | `STT_V2_GATE_1_2_IMPLEMENTATION_BOUNDARY.md` |
| BC-005 | No DOCX/prompt/quick-action scope creep | diff review shows none of these features implemented | git diff proof | Pass | No DOCX/prompt/quick-action/chunking implementation added | `STT_V2_GATE_1_2_IMPLEMENTATION_BOUNDARY.md` |

## 5. Final Verdict

Gate 1 verdict:

```text
Ready
```

Gate 2 verdict:

```text
Ready
```

Overall Gate 1-2 verdict:

```text
Ready for next planning slice
```

## 6. Required Evidence Bundle

Final proof report must attach or cite:

- test command list;
- test outputs;
- runtime config excerpt without secrets;
- capabilities response without secrets;
- synthetic audio fixture metadata;
- artifact store proof;
- no raw provider leak scan;
- backward compatibility proof;
- git diff scope proof.
