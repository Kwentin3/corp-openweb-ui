# STT v2 Gate 2.5 Target Runtime Proof

Status: Gate 2.5 proof report.

Date: 2026-07-02.

## 1. Verdict

```text
Gate 2.5: Pass
Target runtime: root@178.72.138.169:/opt/openwebui-prd0
Server branch/base commit: main @ e89b97e
Deployment source: local workspace source archive
Source archive SHA256: 4ca291d02539d6357e5c3ca27828bcafe32badd9ba0e1276381670f01ba07055
Runtime image id: sha256:0bfc1a22f6aaac0ab727596288613fc3191c3504b15e05db4a9ce6ccf2171df1
```

Gate 1-2 sidecar code was deployed to the target server, rebuilt into the
`compose-stage2-stt` image and the `stage2-stt` container was recreated.

## 2. Changed Runtime Files

Server files replaced from the workspace archive:

- `services/stage2-stt/pyproject.toml`
- `services/stage2-stt/stage2_stt/*`
- `services/stage2-stt/openwebui_actions/*`
- `compose/openwebui.compose.yml`

Server backup before extraction:

```text
/opt/backups/openwebui-prd0/codex-stt-v2/stt-v2-gate25-server-before-20260702T112423Z.tar.gz
```

`.env` was not copied during Gate 2.5 deploy. Server `.env` remains the runtime
source of truth.

## 3. Deploy Commands

```text
tar --exclude='__pycache__' --exclude='.pytest_cache' -czf local/env-sync/stt-v2-gate25-source-20260702T112423Z.tar.gz services/stage2-stt compose/openwebui.compose.yml
scp local/env-sync/stt-v2-gate25-source-20260702T112423Z.tar.gz root@178.72.138.169:/tmp/stt-v2-gate25-source.tar.gz
```

```text
cd /opt/openwebui-prd0
tar --exclude='__pycache__' --exclude='.pytest_cache' -czf /opt/backups/openwebui-prd0/codex-stt-v2/stt-v2-gate25-server-before-20260702T112423Z.tar.gz services/stage2-stt compose/openwebui.compose.yml
tar -xzf /tmp/stt-v2-gate25-source.tar.gz -C /opt/openwebui-prd0
docker compose --env-file .env -f compose/openwebui.compose.yml config --quiet
docker compose --env-file .env -f compose/openwebui.compose.yml build stage2-stt
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --force-recreate stage2-stt
```

Build result:

```text
compose-stage2-stt:latest built
stage2-stt recreated and started
```

## 4. Safe Effective Runtime Config

The target container printed only safe values/statuses:

```text
IMPORT_ARTIFACT_STORE=OK
IMPORT_TRANSCRIPT_STORE=OK
STAGE2_LEMONFOX_API_KEY=SET_NONEMPTY
STAGE2_STT_INTERNAL_API_KEY=SET_NONEMPTY
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true
STAGE2_STT_ARTIFACT_STORE_MODE=sqlite
STAGE2_STT_ARTIFACT_STORE_PATH=/data/stage2-stt/artifacts.sqlite3
STAGE2_STT_ARTIFACT_PAYLOAD_DIR=/data/stage2-stt/artifact-payloads
```

No secret value was printed.

## 5. Capabilities Proof

```text
CAPABILITIES_STATUS=OK
CAP_provider_id='lemonfox'
CAP_adapter_id='lemonfox'
CAP_supports_speaker_labels=True
CAP_artifact_store_mode='sqlite'
CAP_artifact_store_available=True
CAP_storage_mode='auto'
CAP_selected_output_profile='mp3_high_compat'
```

This proves the running container is using the new Gate 1-2 code path: the old
server image did not expose `artifact_store_mode` or `artifact_store_available`.

## 6. Runtime Mount Proof

```text
docker inspect stage2-stt --format '{{.Image}} {{range .Mounts}}{{println .Name .Destination}}{{end}}'
sha256:0bfc1a22f6aaac0ab727596288613fc3191c3504b15e05db4a9ce6ccf2171df1 stage2_stt_data /data/stage2-stt
```

ArtifactStore uses the server-side `stage2_stt_data` volume.

## 7. Transcript Ref Proof

Synthetic two-speaker proof audio:

```text
docs/reports/2026-07-02/STT_V2_GATE_1_2_PROOF_ARTIFACTS/synthetic-two-speaker.wav
```

First probe attempt used `audio/wav` with `mp3_high_compat` and correctly failed
with typed validation:

```text
HTTP 422
code: unsupported_input_format
message: Prepared audio MIME does not match output profile
```

The successful target runtime proof used the same WAV fixture with
`selected_output_profile=wav_pcm_safe`:

```json
{
  "adapter_id": "lemonfox",
  "artifact_store_available": true,
  "artifact_store_mode": "sqlite",
  "distinct_speaker_count": 2,
  "job_status": "completed",
  "provider_id": "lemonfox",
  "ref_only_code": "artifact_scope_unverified",
  "ref_only_status": 403,
  "result_transcript_ref_matches": true,
  "retrieval_ref_matches": true,
  "retrieval_status": 200,
  "segment_count": 4,
  "selected_output_profile": "wav_pcm_safe",
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "status": "ok",
  "supports_speaker_labels": true,
  "transcript_ref_created": true,
  "transcript_ref_len": 47,
  "transcript_ref_prefix": "art_",
  "word_speaker_count": 17,
  "wrong_user_code": "artifact_access_denied",
  "wrong_user_status": 403
}
```

The full `transcript_ref` is intentionally not recorded in this report.

## 8. Artifact Store Proof

SQLite artifact scan on the target runtime:

```json
{
  "artifact_counts": {
    "prepared_audio": 1,
    "source_file": 1,
    "stt_job": 1,
    "transcript_result": 1
  },
  "chain_edge_count": 3,
  "db_contains_api_key": false,
  "db_contains_internal_token": false,
  "db_contains_raw_provider_marker": false,
  "db_exists": true,
  "latest_transcript_payload_keys": [
    "adapter_id",
    "artifact_scope",
    "duration_seconds",
    "job_id",
    "language",
    "output_profile",
    "provider_id",
    "safe_provider_metadata",
    "segments",
    "source_links",
    "text",
    "transcript_hash",
    "transcript_ref",
    "warnings"
  ],
  "latest_transcript_ref_prefix": "art_",
  "latest_transcript_safe_metadata_keys": [
    "adapter_id",
    "provider_id",
    "segment_count",
    "speaker_label_count",
    "transcript_hash"
  ],
  "transcript_index_count": 1
}
```

## 9. Backward Compatibility Proof

Local Action compatibility tests remain green:

```text
cd services/stage2-stt
python -m pytest -q
result: 44 passed
```

The existing Action output remains additive: flat `Transcript:` text is preserved
and `Transcript reference: ...` is appended only when the sidecar returns a valid
opaque ref.

## 10. OpenWebUI Health Proof

```text
docker compose --env-file .env -f compose/openwebui.compose.yml ps
openwebui: Up 5 hours (healthy)
stage2-stt: Up after recreate
```

External HTTPS smoke:

```text
curl -ksS -o /dev/null -w '%{http_code} %{content_type}\n' https://gpt.alpha-soft.ru/
200 text/html; charset=utf-8
```

OpenWebUI core was not patched.

## 11. No-Leak Proof

Checks performed:

- no `.env` copied into the deploy archive;
- runtime probes printed only `SET_NONEMPTY` statuses for secrets;
- SQLite bytes do not contain LemonFox API key;
- SQLite bytes do not contain Stage 2 internal token;
- SQLite bytes do not contain raw-provider markers;
- recent `stage2-stt` logs do not contain `STAGE2_LEMONFOX_API_KEY`,
  `Authorization:`, `Bearer`, `raw_provider`, `raw-lemonfox` or
  `X-Stage2-Internal-Token`.

## 12. Acceptance Status

| Requirement | Status | Evidence |
| --- | --- | --- |
| New Gate 1-2 sidecar code deployed/built on target server | Pass | image `sha256:0bfc1a22...`, imports OK |
| Container runs with new code | Pass | capabilities include artifact-store fields |
| Runtime env has STT v2 artifact settings | Pass | safe env probe |
| Speaker labels enabled | Pass | `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true` |
| Capabilities show speaker support | Pass | `supports_speaker_labels=True` |
| ArtifactStore works on server volume | Pass | `stage2_stt_data /data/stage2-stt`, SQLite rows |
| `transcript_ref` created | Pass | `transcript_ref_created=true` |
| Structured transcript retrieved by ref | Pass | retrieval 200, ref matches |
| Wrong user / missing context fail closed | Pass | `artifact_access_denied`, `artifact_scope_unverified` |
| Flat Action output remains compatible | Pass | local Action tests |
| Ordinary OpenWebUI chat not broken | Pass | OpenWebUI healthy, HTTPS 200 |
| Raw provider/secrets not leaked | Pass | DB/log/report scans |
| `.env` not committed/diffed/report-dumped | Pass | env not included; only statuses recorded |
| OpenWebUI core not patched | Pass | deploy scope limited to sidecar/compose |

## 13. Known Limitations

- The target server working tree is deployed from a workspace source archive
  rather than a committed STT v2 Git SHA. The report records the source archive
  SHA256 and runtime image id; final master delivery should still produce a Git
  commit/push before closeout.
- The proof used `wav_pcm_safe` because the fixture is WAV. The production
  browser path still normally uses `mp3_high_compat` after browser-side
  normalization.
- The sidecar job produced `prepared_audio_storage_transient`; this is existing
  prepared-audio object storage behavior and does not block transcript
  ArtifactStore persistence.

## 14. Final Gate 2.5 Verdict

```text
Gate 2.5: Pass
Next gate allowed: Gate 3 OpenWebUI Prompt Seed & Routing
```
