# STT v2 Gate 1-2 Implementation Proof Report

Status: implementation proof report.

Date: 2026-07-02.

## 1. Summary

```text
Verdict: Ready
Gate 1 verdict: Ready
Gate 2 verdict: Ready
Implementation branch/commit: main working tree, not committed
Runtime target: services/stage2-stt sidecar + OpenWebUI Action extension
```

Gate 2 is implemented and locally proven: structured `TranscriptResultV1` is
stored in an internal SQLite ArtifactStore, `transcript_ref` is opaque and
retrievable through a safe sidecar path, access failures fail closed, and the
flat `Transcript:` Action output remains backward-compatible.

Gate 1 is proven against LemonFox with the synthetic two-speaker fixture after
loading the local `.env` into the proof process and overriding speaker labels
for the proof run:

```text
STAGE2_LEMONFOX_API_KEY_PRESENT=true
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true
```

No secret value is printed or stored in this report.

Server env sync was completed on 2026-07-02. Server `.env` is the source of
truth; local workspace `.env` was replaced from
`root@178.72.138.169:/opt/openwebui-prd0/.env` and hash-matched after sync.
The `stage2-stt` container was recreated with speaker labels enabled and the
STT v2 artifact-store env block mounted into runtime.

## 2. Changed Files

Contracts/models:

- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/runtime.py`

Sidecar routes:

- `services/stage2-stt/stage2_stt/app.py`

Provider adapter:

- `services/stage2-stt/stage2_stt/lemonfox.py` was not changed; existing
  request-form behavior is now test-covered.

Storage:

- `services/stage2-stt/stage2_stt/artifact_store.py`
- `services/stage2-stt/stage2_stt/transcript_store.py`

Action bridge:

- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`

Tests:

- `services/stage2-stt/tests/test_capabilities_endpoint.py`
- `services/stage2-stt/tests/test_config.py`
- `services/stage2-stt/tests/test_job_routes.py`
- `services/stage2-stt/tests/test_lemonfox_adapter.py`
- `services/stage2-stt/tests/test_openwebui_action.py`
- `services/stage2-stt/tests/test_stt_v2_artifact_store.py`

Docs/config/proof:

- `.env.example`
- `compose/openwebui.compose.yml`
- `docs/infra/ENVIRONMENT_VARIABLES.md`
- `docs/stage2/acceptance/STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/config/STT_V2_GATE_1_2_ENV_CONTRACT.md`
- `docs/reports/2026-07-02/STT_V2_GATE_1_2_IMPLEMENTATION_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATE_1_2_PROOF_ARTIFACTS/synthetic-two-speaker.wav`
- `docs/reports/2026-07-02/STT_V2_GATE_1_2_PROOF_ARTIFACTS/artifact-store-proof.sqlite3`

Scope confirmations:

- no OpenWebUI core patch;
- no DOCX implementation;
- no prompt catalog implementation;
- no quick actions/post-processing implementation;
- no chunking implementation.

## 3. Config Used

Safe effective proof config:

```text
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true
STAGE2_STT_ARTIFACT_STORE_MODE=sqlite
STAGE2_STT_TRANSCRIPT_TTL_DAYS=14
STAGE2_STT_PREPARED_AUDIO_TTL_HOURS=24
STAGE2_STT_DIAGNOSTIC_PROVIDER_PAYLOAD_ENABLED=false
STAGE2_LEMONFOX_API_KEY_PRESENT=true
```

Server/workspace sync status:

```text
Server: root@178.72.138.169:/opt/openwebui-prd0
Server checkout: e89b97e
Local .env source: copied from server .env
Local/server .env SHA256 match: true
stage2-stt container recreated: true
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true
STAGE2_STT_ARTIFACT_STORE_MODE=sqlite
STAGE2_STT_ARTIFACT_STORE_PATH=/data/stage2-stt/artifacts.sqlite3
STAGE2_STT_ARTIFACT_PAYLOAD_DIR=/data/stage2-stt/artifact-payloads
STAGE2_STT_TRANSCRIPT_TTL_DAYS=14
STAGE2_STT_TRANSFORMATION_TTL_DAYS=14
STAGE2_STT_PREPARED_AUDIO_TTL_HOURS=24
STAGE2_STT_DIAGNOSTIC_PROVIDER_PAYLOAD_ENABLED=false
STAGE2_STT_ARTIFACT_HARD_DELETE_AFTER_EXPIRY=true
STAGE2_LEMONFOX_API_KEY_PRESENT=true
```

No secrets, API keys, raw env dumps or provider headers are included in this
report.

## 4. Test Commands

```text
cd services/stage2-stt
python -m pytest -q
exit code: 0
result: 44 passed in 1.93s
```

```text
cd services/stage2-stt
python -m pytest -q tests/test_openwebui_action.py tests/test_job_routes.py tests/test_stt_v2_artifact_store.py
exit code: 0
result: 23 passed in 1.51s
```

```text
cd services/stage2-stt
python -m pip install --no-deps . --target %TEMP%/stage2-stt-install-proof-...
exit code: 0
result: packaged artifact contains stage2_stt/artifact_store.py and stage2_stt/transcript_store.py
```

```text
PYTHONPATH=<install-proof-target> python -c "from stage2_stt.artifact_store import ArtifactStoreFactory; from stage2_stt.transcript_store import TranscriptStoreAdapter; print('PACKAGED_IMPORT_OK')"
exit code: 0
result: PACKAGED_IMPORT_OK
```

```text
cd services/stage2-stt
<python proof script loads ../../.env, sets STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true, posts synthetic-two-speaker.wav to LemonFox through sidecar>
exit code: 0
result: LemonFox returned 4 speaker-labeled segments, 2 distinct speakers, transcript_ref retrieved
```

```text
ssh root@178.72.138.169 "docker exec stage2-stt env | grep -E '^(STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS|STAGE2_STT_ARTIFACT_STORE_MODE|STAGE2_STT_ARTIFACT_STORE_PATH|STAGE2_STT_ARTIFACT_PAYLOAD_DIR|STAGE2_STT_TRANSCRIPT_TTL_DAYS|STAGE2_STT_DIAGNOSTIC_PROVIDER_PAYLOAD_ENABLED)='"
exit code: 0
result: server container has STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true and STAGE2_STT_ARTIFACT_STORE_MODE=sqlite
```

```text
ssh root@178.72.138.169 "docker inspect stage2-stt --format '{{range .Mounts}}{{println .Name .Destination}}{{end}}'"
exit code: 0
result: stage2_stt_data /data/stage2-stt
```

```text
docker exec -i stage2-stt python - <capability probe>
exit code: 0
result: provider_id='lemonfox', adapter_id='lemonfox', supports_speaker_labels=True, selected_output_profile='mp3_high_compat', storage_mode='auto'
```

```text
scp root@178.72.138.169:/opt/openwebui-prd0/.env .env
Get-FileHash .env and remote sha256sum /opt/openwebui-prd0/.env
exit code: 0
result: local/server .env SHA256 match true; API key status only: SET_NONEMPTY
```

```text
ssh root@178.72.138.169 "cd /opt/openwebui-prd0 && docker compose --env-file .env -f compose/openwebui.compose.yml config --quiet"
exit code: 0
result: server compose config valid after env/volume sync
```

```text
rg -n "services/.*/src|\\.\\./\\.\\./|process\\.cwd\\(|path\\.resolve\\(process\\.cwd|config/.*\\.json|secrets/.*\\.json|\\.\\./\\.\\./config|dev\\.json|prod\\.json" services/stage2-stt
exit code: 1
result: no matches
```

```text
git diff --check -- services/stage2-stt
exit code: 0
result: no whitespace errors; Git reported expected LF-to-CRLF working-copy warnings
```

## 5. Gate 1 Diarization Proof

Runtime flag/capability proof from sidecar proof script:

```json
{
  "supports_speaker_labels": true,
  "artifact_store_mode": "sqlite",
  "artifact_store_available": true,
  "warnings": [
    "prepared_audio_storage_transient",
    "lemonfox_api_key_absent_live_calls_disabled",
    "provider_max_duration_unknown",
    "provider_cancel_unknown_local_cancel_only"
  ]
}
```

Provider request parameter proof:

- `test_lemonfox_request_form_enables_speaker_labels_and_verbose_json`
  asserts `speaker_labels=true`;
- the same test asserts `response_format=verbose_json`;
- the same test asserts `timestamp_granularities[]=word` when timestamps are
  enabled.

Synthetic fixture proof:

```text
Path: docs/reports/2026-07-02/STT_V2_GATE_1_2_PROOF_ARTIFACTS/synthetic-two-speaker.wav
Generation: Windows System.Speech TTS, alternating Microsoft David Desktop and Microsoft Zira Desktop
Content:
  Project alpha starts on Monday.
  I will prepare the checklist.
  Please confirm the deployment window.
  The deployment window is Thursday morning.
Duration seconds: 11.741043
Size bytes: 517826
SHA256: 2E433FFB0B78C1075A210BB8A972BF364C36DDED8A17971B2CC08150C8111510
```

Normalized speaker-field proof:

- `test_lemonfox_normalizes_speaker_labels_without_raw_payload_leak`;
- `test_transcript_store_persists_structured_transcript_and_lineage`;
- segment speakers and word speakers are preserved when provider-shaped verbose
  JSON contains them.

Live synthetic audio provider proof:

```json
{
  "created_status": 200,
  "distinct_segment_speakers": [
    "SPEAKER_00",
    "SPEAKER_01"
  ],
  "retrieved_status": 200,
  "segment_count": 4,
  "segment_speaker_count": 4,
  "transcript_ref_prefix": "art_",
  "word_speaker_count": 17
}
```

The full safe summary is stored at:

```text
docs/reports/2026-07-02/STT_V2_GATE_1_2_PROOF_ARTIFACTS/live-lemonfox-diarization-summary.json
```

## 6. Gate 2 Artifact-store Proof

Sidecar proof script result:

```json
{
  "created_status": 200,
  "job_status": "completed",
  "transcript_ref_prefix": "art_",
  "retrieved_status": 200,
  "retrieved_has_hash": true,
  "wrong_user": {
    "status": 403,
    "code": "artifact_access_denied"
  },
  "no_context": {
    "status": 403,
    "code": "artifact_scope_unverified"
  },
  "sqlite_counts": {
    "artifact_records": 4,
    "artifact_edges": 3,
    "transcript_index": 1
  },
  "no_secret_or_raw_marker": true
}
```

The proof database is:

```text
docs/reports/2026-07-02/STT_V2_GATE_1_2_PROOF_ARTIFACTS/artifact-store-proof.sqlite3
```

Implemented store behavior:

- `ArtifactStoreFactory` is the production entrypoint;
- `SqliteArtifactStoreAdapter` creates `artifact_records`,
  `artifact_edges` and `transcript_index`;
- `TranscriptStoreAdapter` writes source-file, prepared-audio, STT-job and
  transcript-result records;
- `transcript_ref` is an `art_...` opaque ref;
- access validation requires matching available context fields;
- ref-only access returns `artifact_scope_unverified`;
- wrong user returns `artifact_access_denied`;
- expired refs return `artifact_expired`.

## 7. Backward Compatibility Proof

Flat Action output proof:

- `test_action_returns_backward_compatible_flat_transcript_with_safe_ref`
  asserts content starts with `Transcript:\n\nhello transcript`;
- the visible `Transcript reference: \`art_...\`` line is additive and contains
  only an opaque ref;
- no raw sidecar JSON is rendered by the Action.

Artifact-store failure behavior:

- default artifact store mode is `disabled`;
- `test_job_route_creates_completed_stub_job_and_exposes_result` proves a
  successful STT job still returns result text and no fake `transcript_ref`;
- response warnings include `artifact_store_unavailable`.

Base chat availability:

- artifact retrieval is isolated to
  `GET /stage2-api/transcription/transcripts/{transcript_ref}`;
- retrieval failure returns typed HTTP errors and does not affect ordinary chat
  or the existing job result path.

## 8. No-secrets / No Raw Provider Leak Proof

Tests:

- `test_lemonfox_normalizes_speaker_labels_without_raw_payload_leak`;
- `test_provider_raw_payload_marker_is_not_stored_in_product_artifacts`;
- `test_runtime_capabilities_endpoint_does_not_expose_secrets`;
- `test_action_returns_backward_compatible_flat_transcript_with_safe_ref`.

Code/proof observations:

- product artifacts store normalized `TranscriptResultV1`, not raw LemonFox JSON;
- diagnostic provider payload storage is rejected by config validation for
  Gate 1-2;
- proof SQLite scan returned `no_secret_or_raw_marker=true`;
- no ordinary logging path prints transcript payloads or provider JSON.

## 9. Acceptance Matrix Closure

Source matrix:

```text
docs/stage2/acceptance/STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md
```

Row closure:

| ID | Status |
| --- | --- |
| G1-DIA-001 | Pass |
| G1-DIA-002 | Pass |
| G1-DIA-003 | Pass |
| G1-DIA-004 | Pass |
| G1-DIA-005 | Pass |
| G1-DIA-006 | Pass |
| G1-DIA-007 | Pass |
| G1-DIA-008 | Pass |
| G1-DIA-009 | Pass |
| G1-DIA-010 | Pass |
| G2-ART-001 | Pass |
| G2-ART-002 | Pass |
| G2-ART-003 | Pass |
| G2-ART-004 | Pass |
| G2-ART-005 | Pass |
| G2-ART-006 | Pass |
| G2-ART-007 | Pass |
| G2-ART-008 | Pass |
| G2-ART-009 | Pass |
| G2-ART-010 | Pass |
| G2-ART-011 | Pass |
| G2-ART-012 | Pass |
| G2-ART-013 | Pass |
| G2-ART-014 | Pass |
| G2-ART-015 | Pass |
| G2-ART-016 | Pass |
| BC-001 | Pass |
| BC-002 | Pass |
| BC-003 | Pass |
| BC-004 | Pass |
| BC-005 | Pass |

## 10. Known Limitations

- Server `.env` and local workspace `.env` now have
  `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true`.
- Server compose/env is prepared for the STT v2 artifact store. Full Gate 2
  runtime on the server still requires deploying/rebuilding the sidecar code
  from this implementation tree; the current server checkout observed during
  env sync was `e89b97e`.
- Stub-mode sidecar proof remains useful for route/storage/access behavior but
  live provider proof is now separately recorded.
- No prompt catalog.
- No quick actions.
- No DOCX.
- No chunking.
- No object-storage URL provider path.
- No separate transcript history UI.

## 11. Open Questions

| Question | Owner | Next Action |
| --- | --- | --- |
| Should diarization become default-on after proof? | product/ops | Decide after live provider proof and cost/quality review |

## 12. Final Verdict

```text
Gate 1: Ready
Gate 2: Ready
Overall: Ready for next planning slice
Rationale: live LemonFox synthetic diarization, structured transcript preservation, safe transcript_ref access, no raw-provider leak checks and backward compatibility proofs pass
Next recommended gate: Gate 3 structured transcript preservation through OpenWebUI Action/loader boundary or prompt catalog planning
```
