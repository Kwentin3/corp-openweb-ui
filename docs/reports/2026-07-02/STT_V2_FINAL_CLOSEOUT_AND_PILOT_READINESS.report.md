# STT v2 Final Closeout And Pilot Readiness

Status: final MVP closeout before manual browser testing and controlled pilot.

Date: 2026-07-02.

Final verdict:

```text
READY_FOR_MANUAL_BROWSER_TEST
```

## 1. Executive Summary

STT v2 MVP post-processing is ready for manual browser testing on the production
OpenWebUI contour.

Current implemented contour:

```text
OpenWebUI chat
-> media upload / native Action
-> stage2-stt sidecar
-> LemonFox STT provider adapter
-> normalized TranscriptResultV1
-> SQLite ArtifactStore transcript_ref
-> OpenWebUI Prompt-backed post-processing catalog
-> two quick actions
-> OpenAI-compatible post-processing executor
-> processed result returned to the same chat
```

Fresh closeout probes confirmed:

- OpenWebUI container is running and healthy.
- `stage2-stt` container is running.
- external HTTPS entrypoint returns 200.
- sidecar exposes current STT v2 capabilities.
- ArtifactStore is available in SQLite mode.
- Prompt catalog mode is the accepted MVP mode: `openwebui_sqlite`.
- two MVP prompt templates are available without prompt body leakage.
- provider egress from `stage2-stt` returns 200.
- installed OpenWebUI Action can list both quick actions.
- installed OpenWebUI Action can execute both MVP post-processing actions.
- direct sidecar post-processing execution works for both MVP templates.
- recent OpenWebUI and `stage2-stt` logs do not contain secret/raw markers.
- local STT sidecar tests pass.

Authenticated browser-click proof was not performed by the agent because no safe
interactive user browser session or test credential was available in this
environment. This is a controlled limitation, not a pilot blocker: the runtime
bridge is proven through loader hash, installed Action execution and sidecar
probes, and a manual browser test program is prepared for the user.

## 2. Source Of Truth Reviewed

Blueprint:

- `docs/stage2/blueprints/STT_V2_TRANSCRIPT_POSTPROCESSING.blueprint.md`

Gate reports:

- `docs/reports/2026-07-02/STT_V2_GATE_1_2_IMPLEMENTATION_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATE_2_5_TARGET_RUNTIME_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATE_3_PROMPT_CATALOG_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATE_4_QUICK_ACTIONS_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATE_5_PROMPT_ACCESS_VERSION_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATED_DELIVERY_MASTER_PROOF.report.md`

Research:

- `docs/reports/2026-07-02/STT_V2_OPENWEBUI_PROMPT_API_ADAPTER_RESEARCH.report.md`

Closeout handoff docs:

- `docs/stage2/operations/STT_V2_MVP_OPERATOR_NOTES.md`
- `docs/stage2/operations/STT_V2_MANUAL_BROWSER_TEST_PROGRAM.md`
- `docs/stage2/operations/STT_V2_PILOT_READINESS_CHECKLIST.md`

## 3. Current Runtime Status

Target checkout:

```text
branch=main
commit=e89b97e
```

Compose/runtime status:

```text
openwebui: running, healthy
stage2-stt: running
traefik: running
external HTTPS smoke: 200 text/html
```

Safe `stage2-stt` effective config:

```text
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true
STAGE2_STT_ARTIFACT_STORE_MODE=sqlite
STAGE2_STT_PROMPT_CATALOG_MODE=openwebui_sqlite
STAGE2_STT_POSTPROCESSING_EXECUTOR_MODE=openai_compatible
STAGE2_STT_POSTPROCESSING_OPENAI_MODEL=gpt-5.4-mini
STAGE2_STT_POSTPROCESSING_MAX_TRANSCRIPT_CHARS=60000
```

Secret status only:

```text
STAGE2_STT_INTERNAL_API_KEY: present
STAGE2_LEMONFOX_API_KEY: present
STAGE2_STT_POSTPROCESSING_OPENAI_API_KEY: present
```

Sidecar package proof:

```text
stage2_stt package root: /app/stage2_stt
python file count: 17
key files present: app.py, artifact_store.py, transcript_store.py,
  prompt_catalog.py, post_processing.py
package manifest sha256: 4829059e32265cb673f236903c83ad4b37ad1115355c4c8ca0ffa998c16c6328
```

Loader and Action proof:

```text
loader exists in OpenWebUI container: true
loader sha256: 314c469ae2d9d682419ab35b392559e8901dfaf667740da3f41194649df30d85
OpenWebUI Action id: stage2_media_transcription_action
Action active: true
Action content sha256: 24b97d75d43133d1790caf694f42fea92820cd87cc016bad22e5f1627b899295
Action has list operation: true
Action has execute operation: true
Action valves configured: true
```

Proxy parity:

- OpenWebUI and `stage2-stt` both have effective HTTP(S) proxy and no-proxy
  settings.
- This remains important because provider egress parity was the Gate 4 blocker.
- Proxy values are intentionally not copied into this report.

## 4. Gates Status Table

| Gate | Status | Evidence |
| --- | --- | --- |
| Gate 1 | Closed | LemonFox speaker-label capability and synthetic proof in Gate 1-2 report |
| Gate 2 | Closed | `TranscriptResultV1` preservation and ArtifactStore proof in Gate 1-2 report |
| Gate 2.5 | Closed | target runtime deploy/proof report |
| Gate 3 | Closed | two OpenWebUI Prompt templates and SQLite catalog proof |
| Gate 4 | Closed | quick-action bridge, post-processing execution and provider egress proof |
| Gate 5 | Closed | prompt access/version/deleted/change/old-result proof |
| Gate 6 | Closed for MVP | refusal-only long transcript policy, `transcript_too_long_single_pass` |
| Gate 7 | Deferred | future chunking enhancement |
| Gate 8 | Deferred | future DOCX export gate |

## 5. Implemented Scope

Implemented and proven:

- normalized `TranscriptResultV1`;
- speaker-label capability enabled in runtime;
- SQLite ArtifactStore for product transcript and post-processing artifacts;
- opaque `transcript_ref`;
- access-scoped transcript retrieval;
- backward-compatible flat `Transcript:` output;
- OpenWebUI Prompt-backed post-processing catalog;
- read-only SQLite PromptCatalogAdapter as MVP/default;
- two MVP prompt templates;
- quick-action list and execute bridge through native OpenWebUI Action;
- static loader helper with safe degradation;
- OpenAI-compatible post-processing executor;
- prompt version/hash capture;
- old processed result version/hash preservation;
- long transcript safe refusal.

## 6. Explicitly Deferred Scope

Deferred by design:

- DOCX export;
- chunking/map-reduce;
- OpenWebUI Prompt API Adapter;
- replacing SQLite PromptCatalogAdapter;
- full set of 8 prompt templates;
- separate Meetings app;
- separate transcript history UI;
- CRM/task tracker integration;
- public URL/object storage upload path for large provider files.

These are not blockers for the controlled pilot.

## 7. Fresh Closeout Proof

### 7.1 Capabilities

Fresh sidecar capabilities probe:

```json
{
  "status": 200,
  "provider_id": "lemonfox",
  "adapter_id": "lemonfox",
  "artifact_store_mode": "sqlite",
  "artifact_store_available": true,
  "supports_speaker_labels": true,
  "storage_mode": "auto",
  "storage_available": false,
  "max_prepared_audio_mb": 100,
  "warnings": [
    "prepared_audio_storage_transient",
    "provider_max_duration_unknown",
    "provider_cancel_unknown_local_cancel_only"
  ]
}
```

`storage_available=false` here is not an ArtifactStore failure. The MVP stores
product transcript/result artifacts in SQLite and keeps prepared audio storage
transient.

### 7.2 Prompt Catalog

Fresh prompt catalog probe:

```json
{
  "status": 200,
  "template_count": 2,
  "prompt_body_leaked": false,
  "templates": [
    {
      "template_id": "stage2.stt.summary.v1",
      "command": "stt-summary",
      "prompt_hash_len": 64,
      "prompt_version_present": true,
      "openwebui_prompt_id_present": true
    },
    {
      "template_id": "stage2.stt.meeting_protocol.v1",
      "command": "stt-meeting-protocol",
      "prompt_hash_len": 64,
      "prompt_version_present": true,
      "openwebui_prompt_id_present": true
    }
  ]
}
```

### 7.3 Provider Egress

Fresh provider connectivity probe from `stage2-stt`:

```json
{
  "status": 200,
  "ok": true
}
```

### 7.4 Sidecar Post-processing Execution

Fresh direct sidecar execution against the latest valid transcript artifact:

```json
[
  {
    "template_id": "stage2.stt.summary.v1",
    "status": 200,
    "result_ref_prefix": "art_",
    "result_ref_len": 47,
    "text_len": 151,
    "prompt_hash_len": 64,
    "prompt_version_present": true,
    "transcript_ref_matches": true,
    "body_or_secret_marker_found": false
  },
  {
    "template_id": "stage2.stt.meeting_protocol.v1",
    "status": 200,
    "result_ref_prefix": "art_",
    "result_ref_len": 47,
    "text_len": 626,
    "prompt_hash_len": 64,
    "prompt_version_present": true,
    "transcript_ref_matches": true,
    "body_or_secret_marker_found": false
  }
]
```

### 7.5 Installed OpenWebUI Action List Operation

Fresh installed Action list operation:

```json
{
  "templates_count": 2,
  "template_commands": [
    "stt-summary",
    "stt-meeting-protocol"
  ],
  "content_empty": true,
  "prompt_body_leaked": false,
  "secret_marker_found": false,
  "status_events": [
    ["Loading transcript actions...", false],
    ["Transcript actions loaded.", true]
  ]
}
```

### 7.6 Installed OpenWebUI Action Execute Operation

Fresh installed Action execute operation for both MVP actions:

```json
{
  "status": "ok",
  "results": [
    {
      "template_id": "stage2.stt.summary.v1",
      "content_len": 254,
      "has_result_ref": true,
      "safe_failure": false,
      "secret_marker_found": false,
      "prompt_body_marker_found": false
    },
    {
      "template_id": "stage2.stt.meeting_protocol.v1",
      "content_len": 687,
      "has_result_ref": true,
      "safe_failure": false,
      "secret_marker_found": false,
      "prompt_body_marker_found": false
    }
  ],
  "events": [
    ["Running transcript action...", false],
    ["Transcript action complete.", true],
    ["Running transcript action...", false],
    ["Transcript action complete.", true]
  ]
}
```

This proves the installed OpenWebUI Action can call the sidecar and return both
processed results through the same Action bridge.

### 7.7 ArtifactStore And No-leak Scan

Fresh ArtifactStore scan:

```json
{
  "artifact_type_counts": {
    "post_processing_result": 5,
    "prepared_audio": 1,
    "source_file": 1,
    "stt_job": 1,
    "transcript_result": 1
  },
  "secret_or_raw_markers_found": false
}
```

Markers scanned in the artifact DB included API-key names, internal token names,
authorization markers and raw-provider markers. None were found.

Fresh recent log scan:

```json
{
  "stage2-stt": {
    "bytes_scanned": 768,
    "any_marker_hit": false
  },
  "openwebui": {
    "bytes_scanned": 1029,
    "any_marker_hit": false
  }
}
```

Markers included API-key names, token header names, authorization markers and
raw-provider markers. None were found.

### 7.8 Local Validation

Fresh local validation:

```text
python -m pytest -q services/stage2-stt/tests
result: 64 passed in 3.38s

node --check deploy/openwebui-static/loader.js
result: pass
```

## 8. Browser Smoke Proof Result

Authenticated browser-click proof was **not completed by the agent**.

Reason:

- no safe authenticated browser session or dedicated test credential was
  available to the agent;
- using or creating a real user session from the agent would add avoidable
  credential-handling risk.

Controlled substitute proof:

- static loader hash verified in OpenWebUI container;
- installed Action list operation executed successfully;
- installed Action execute operation executed both MVP templates successfully;
- direct sidecar prompt catalog and post-processing probes are green;
- manual browser test program is prepared for the user.

Manual test program:

- `docs/stage2/operations/STT_V2_MANUAL_BROWSER_TEST_PROGRAM.md`

This satisfies the closeout option B: manual browser proof is prepared, and the
runtime bridge has been proven through loader hash, Action execution and sidecar
probes.

## 9. Main User Scenario Readiness

Prepared user scenario:

```text
user opens OpenWebUI chat
-> uploads audio/video
-> starts transcription
-> receives Transcript in the same chat
-> sees/uses post-processing actions
-> chooses Краткий пересказ
-> receives result in the same chat
-> chooses Протокол встречи
-> receives result in the same chat
```

Current proof status:

| Step | Status |
| --- | --- |
| OpenWebUI loads | Proven by external HTTPS smoke |
| `stage2-stt` sidecar runs | Proven by compose status and capabilities |
| transcription path works | Proven by Gate 1-2 / Gate 2.5 |
| transcript_ref is created | Proven by Gate 2.5 and current ArtifactStore |
| quick-action list bridge works | Proven by installed Action list operation |
| `Краткий пересказ` works | Proven by installed Action execute operation |
| `Протокол встречи` works | Proven by installed Action execute operation |
| result returns through Action bridge | Proven by Action execute result refs |
| manual browser click path | Prepared, to be run by user |

## 10. Backward Compatibility

Confirmed:

- old flat `Transcript:` output remains in Action code and tests;
- local Action tests pass;
- ordinary OpenWebUI container remains healthy;
- external OpenWebUI entrypoint returns 200;
- failures in sidecar/Action paths are formatted as safe chat content;
- loader is optional and designed to degrade safely;
- OpenWebUI core was not patched.

## 11. Safety / No-leak Confirmation

Confirmed by existing gate reports and fresh closeout probes:

- raw LemonFox JSON is not a product artifact;
- raw LemonFox JSON is not returned in Action output;
- raw LemonFox JSON is not returned in loader/browser metadata;
- raw LemonFox JSON is not present in ordinary scanned logs;
- raw LemonFox/provider markers are not present in ArtifactStore DB bytes scan;
- secrets/tokens are recorded only as `SET_NONEMPTY` statuses;
- prompt body is not returned in quick-action metadata;
- prompt body is not stored in post-processing result artifacts;
- full rendered prompt body is not stored by default;
- final docs do not include prompt bodies or token values.

## 12. Operator Notes Summary

Operator notes location:

- `docs/stage2/operations/STT_V2_MVP_OPERATOR_NOTES.md`

Key operator facts:

- `stage2-stt` is the sidecar service in the OpenWebUI compose stack.
- ArtifactStore is SQLite-backed.
- Prompt catalog MVP/default is `openwebui_sqlite`.
- provider proxy/no-proxy parity between OpenWebUI and `stage2-stt` is required.
- capabilities, prompt catalog, quick actions and post-processing have separate
  checks.
- safe restart is a sidecar compose recreate after compose config validation.
- logs may be inspected only after avoiding secret/raw payload disclosure.

## 13. Pilot-readiness Checklist

Checklist location:

- `docs/stage2/operations/STT_V2_PILOT_READINESS_CHECKLIST.md`

Current closeout status:

```text
[x] OpenWebUI доступен
[x] stage2-stt доступен
[x] транскрибация работает
[x] transcript_ref создаётся
[x] ArtifactStore работает
[x] два prompt-шаблона существуют
[x] quick actions доступны
[x] `Краткий пересказ` работает
[x] `Протокол встречи` работает
[x] long transcript получает safe refusal
[x] DOCX отсутствует by design
[x] chunking отсутствует by design
[x] SQLite PromptCatalogAdapter accepted as MVP/default
[x] OpenWebUI API Adapter отложен
[x] secrets не светятся
[x] OpenWebUI core не патчился
[x] known limitations записаны
```

The checklist is intentionally provided as unchecked in the handoff file so it
can be reused before each pilot run.

## 14. Known Limitations

Known MVP limitations, not blockers:

- DOCX export is not implemented.
- Chunking/map-reduce is not implemented.
- OpenWebUI Prompt API Adapter is deferred.
- SQLite PromptCatalogAdapter is accepted as MVP/default.
- Only two MVP templates are implemented.
- Full set of 8 templates is deferred.
- Authenticated browser-click proof was replaced by manual browser test program
  plus runtime bridge proof.
- Prepared audio payload storage remains transient; product transcript and
  post-processing artifacts are stored.
- Long transcript behavior is refusal-only in MVP mode.

## 15. Stop-condition Review

| Stop condition | Result |
| --- | --- |
| OpenWebUI unavailable | Not hit |
| `stage2-stt` unavailable | Not hit |
| quick actions unavailable without fallback | Not hit |
| post-processing execution broken | Not hit |
| old flat transcript workflow broken | Not hit |
| provider egress broken | Not hit |
| secrets/raw provider payload visible | Not hit |
| OpenWebUI core patch required | Not hit |
| work drifted into DOCX/chunking/API adapter | Not hit |

## 16. Final Verdict

```text
READY_FOR_MANUAL_BROWSER_TEST
```

The STT v2 MVP post-processing contour is closed for controlled pilot
preparation. The next action is manual browser testing using:

```text
docs/stage2/operations/STT_V2_MANUAL_BROWSER_TEST_PROGRAM.md
```
