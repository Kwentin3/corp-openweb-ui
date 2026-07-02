# STT v2 Gate 4 Quick Actions Proof

Status: Gate 4 proof report.

Date: 2026-07-02.

## 1. Verdict

```text
Gate 4: Pass
Target runtime: root@178.72.138.169:/opt/openwebui-prd0
Server branch/base commit: main @ e89b97e
Deployment source archive SHA256: 71f7810c16734bae4d9cd1866b67dc07311d7dedb6dfff8e741df2c684b541a0
Runtime image id: sha256:44e81ffc1eeb676ae3f4bbfe018627d518dd19a80940d42db8089e4998a0f60e
```

The quick-action bridge is implemented and deployed. The static loader exposes
two post-processing actions, the native OpenWebUI Action delegates through the
sidecar, the sidecar resolves OpenWebUI Prompt references, and both MVP actions
successfully produce stored `PostProcessingResultV1` artifacts on target runtime.

## 2. Runtime Deployment

Server backup before Gate 4 source deploy:

```text
/opt/backups/openwebui-prd0/codex-stt-v2/stt-v2-gate4-server-before-20260702T115147Z.tar.gz
```

OpenWebUI Action DB backup before native function update:

```text
/app/backend/data/runtime-backups/webui-before-stt-v2-gate4-action-20260702T115147Z.db
```

Compose backup before stage2-stt proxy parity fix:

```text
/opt/backups/openwebui-prd0/codex-stt-v2/openwebui.compose.yml.before-stage2-proxy-20260702T1220PROXY
```

Runtime status:

```text
openwebui_health=healthy running
stage2_status=running
external=200 text/html; charset=utf-8
```

Loader proof:

```text
loader_host=314c469ae2d9d682419ab35b392559e8901dfaf667740da3f41194649df30d85  deploy/openwebui-static/loader.js
loader_container=314c469ae2d9d682419ab35b392559e8901dfaf667740da3f41194649df30d85  /app/backend/open_webui/static/loader.js
```

OpenWebUI Action function proof:

```json
{
  "action_content_sha256": "24b97d75d43133d1790caf694f42fea92820cd87cc016bad22e5f1627b899295",
  "content_len": 17742,
  "has_execute": true,
  "has_list": true,
  "valves_len": 606
}
```

Valves were preserved; secret values were not printed.

## 3. Provider Egress Fix

Initial Gate 4 execution failed only from `stage2-stt`: OpenWebUI had outbound
proxy env, but `stage2-stt` did not. The fix was to pass the same
`OPENWEBUI_OUTBOUND_PROXY` and `OPENWEBUI_NO_PROXY` values into `stage2-stt`
through compose. This keeps provider egress parity without patching OpenWebUI
core or adding a new executor.

Safe runtime config after recreate:

```text
STAGE2_STT_PROMPT_CATALOG_MODE=openwebui_sqlite
STAGE2_STT_POSTPROCESSING_EXECUTOR_MODE=openai_compatible
STAGE2_STT_POSTPROCESSING_OPENAI_BASE_URL=https://api.openai.com/v1
STAGE2_STT_POSTPROCESSING_OPENAI_API_KEY=SET_NONEMPTY
STAGE2_STT_POSTPROCESSING_OPENAI_MODEL=gpt-5.4-mini
STAGE2_STT_POSTPROCESSING_MAX_TRANSCRIPT_CHARS=60000
http_proxy=http://172.18.0.1:8118
https_proxy=http://172.18.0.1:8118
```

No `.env` secret value is included in this report.

Provider probe from inside `stage2-stt` after the fix:

```json
{
  "direct_provider_status": 200,
  "direct_provider_text_len": 2
}
```

## 4. Sidecar Execution Proof

Execution used the persisted Gate 2.5 `TranscriptResultV1` artifact and the two
native OpenWebUI Prompt-backed templates.

```json
{
  "artifact_type_counts": {
    "post_processing_result": 2,
    "prepared_audio": 1,
    "source_file": 1,
    "stt_job": 1,
    "transcript_result": 1
  },
  "direct_provider_status": 200,
  "executions": [
    {
      "command": "stt-summary",
      "contains_secret_marker": false,
      "openwebui_prompt_id_present": true,
      "prompt_hash_len": 64,
      "prompt_version_present": true,
      "result_ref_len": 47,
      "result_ref_prefix": "art_",
      "status": 200,
      "template_id": "stage2.stt.summary.v1",
      "text_len": 151,
      "transcript_ref_matches": true
    },
    {
      "command": "stt-meeting-protocol",
      "contains_secret_marker": false,
      "openwebui_prompt_id_present": true,
      "prompt_hash_len": 64,
      "prompt_version_present": true,
      "result_ref_len": 47,
      "result_ref_prefix": "art_",
      "status": 200,
      "template_id": "stage2.stt.meeting_protocol.v1",
      "text_len": 631,
      "transcript_ref_matches": true
    }
  ],
  "stored_post_processing": [
    {
      "artifact_ref_len": 47,
      "artifact_ref_prefix": "art_",
      "parent_has_transcript": true,
      "payload_has_prompt_body_marker": false,
      "payload_has_provider_payload": false,
      "safe_metadata_keys": [
        "command",
        "openwebui_prompt_id",
        "prompt_body_hash",
        "prompt_version",
        "template_id",
        "transcript_hash"
      ],
      "size_bytes": 1021
    },
    {
      "artifact_ref_len": 47,
      "artifact_ref_prefix": "art_",
      "parent_has_transcript": true,
      "payload_has_prompt_body_marker": false,
      "payload_has_provider_payload": false,
      "safe_metadata_keys": [
        "command",
        "openwebui_prompt_id",
        "prompt_body_hash",
        "prompt_version",
        "template_id",
        "transcript_hash"
      ],
      "size_bytes": 255
    }
  ],
  "stored_secret_markers_found": false,
  "template_count": 2,
  "templates_status": 200,
  "token_printed": false
}
```

This proves successful prompt execution, result persistence, parent transcript
linking, prompt id/version/hash capture, and no prompt body/provider payload
storage in product artifacts.

## 5. Quick Action Bridge Proof

Runtime Action was executed from the installed OpenWebUI `function` table,
inside the OpenWebUI container, using its existing valves.

```json
{
  "execute_content_len": 254,
  "execute_has_result_ref": true,
  "execute_safe_failure": false,
  "secret_markers_found": false,
  "status_events": [
    [
      "Loading transcript actions...",
      false
    ],
    [
      "Transcript actions loaded.",
      true
    ],
    [
      "Running transcript action...",
      false
    ],
    [
      "Transcript action complete.",
      true
    ]
  ],
  "template_commands": [
    "stt-summary",
    "stt-meeting-protocol"
  ],
  "templates_count": 2
}
```

This proves the same-chat Action bridge can list the two quick actions and
return a successful processed result reference without exposing secrets.

## 6. Long Transcript Policy

Gate 4 does not implement chunking. The runtime policy is explicit single-pass
with typed refusal above `STAGE2_STT_POSTPROCESSING_MAX_TRANSCRIPT_CHARS`.

Target runtime proof:

```json
{
  "cleanup_scope": "done",
  "code": "transcript_too_long_single_pass",
  "input_chars": 60100,
  "max_chars": 60000,
  "status": 413,
  "transcript_ref_len": 47,
  "transcript_ref_prefix": "art_"
}
```

The temporary long-transcript artifact scope was then cleaned up:

```json
{
  "scope_id": "scope_211a9ed261e3fcfcecc41c5fa49ff7a2",
  "active_after_cleanup": 0
}
```

## 7. Tests

```text
python -m pytest -q services/stage2-stt/tests/test_openwebui_action.py
result: 9 passed in 0.56s

python -m pytest -q services/stage2-stt/tests/test_prompt_catalog.py services/stage2-stt/tests/test_post_processing.py services/stage2-stt/tests/test_post_processing_routes.py
result: 16 passed in 2.04s

python -m pytest -q services/stage2-stt/tests
result: 64 passed in 3.46s

node --check deploy/openwebui-static/loader.js
result: pass
```

`git diff --check -- . ':!services/stage2-stt/build'` returned only existing
LF-to-CRLF warnings from Git on Windows.

## 8. Acceptance Status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Two quick actions available after transcription | Pass | loader and Action list proof show two templates |
| Actions reference prompt metadata, not prompt body | Pass | `has_body_field=false`; no prompt body in loader/Action |
| Uses structured transcript projection | Pass | `PostProcessingService` uses `TranscriptStoreAdapter` and normalized projection; tests cover normalized-only render |
| Speaker-aware projection when labels exist | Pass | projection test and Gate 2.5 speaker-labeled transcript proof |
| Same-chat workflow bridge | Pass | Action returns successful processed content with result ref |
| `PostProcessingResultV1` stored on success | Pass | target artifact count and stored result rows |
| prompt id/version/hash captured | Pass | target execution proof |
| no raw provider payload/secrets in browser/chat/artifacts | Pass | no-leak probes and stored payload checks |
| flat `Transcript:` output backward compatible | Pass | Action default transcription path preserved; tests pass |
| artifact/transcript failures do not break chat | Pass | Action catches HTTP status and returns safe content; tests cover failure paths |
| typed errors | Pass | `prompt_not_found`, `prompt_access_denied`, `artifact_scope_unverified`, `postprocessing_execution_failed`, `transcript_too_long_single_pass` |
| OpenWebUI core not patched | Pass | static loader bind mount, native Action DB update and sidecar compose only |
| loader safe-to-fail | Pass | syntax check, status restoration tests, runtime success/failure proof |
| no DOCX/chunking | Pass | no DOCX code; long transcript refuses with 413 |

## 9. Known Limitations

- The current loader proof is code/runtime bridge proof, not an authenticated
  Playwright browser-click proof. Runtime Action execution covers the native
  Action path and sidecar behavior.

## 10. Final Gate 4 Verdict

```text
Gate 4: Pass
Next gate allowed: Gate 5 Prompt Access, Version And Change Behavior
```
