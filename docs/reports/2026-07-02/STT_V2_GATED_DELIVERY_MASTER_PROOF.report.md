# STT v2 Gated Delivery Master Proof

Status: master proof report for Gate 2.5, Gate 3, Gate 4 and Gate 5.

Date: 2026-07-02.

## 1. Final Verdict

```text
Master goal: Pass
Gate 2.5: Pass
Gate 3: Pass
Gate 4: Pass
Gate 5: Pass
Target runtime: root@178.72.138.169:/opt/openwebui-prd0
Server branch/base commit: main @ e89b97e
```

The STT v2 extension layer is deployed without OpenWebUI core patches. The
browser loader, native Action, sidecar routes, prompt catalog adapter,
post-processing service, artifact persistence and access checks are in place.

The last Gate 4 blocker was provider egress parity: OpenWebUI had outbound
proxy env, while `stage2-stt` did not. Passing the same
`OPENWEBUI_OUTBOUND_PROXY` and `OPENWEBUI_NO_PROXY` into `stage2-stt` restored
provider access and allowed successful target-runtime post-processing.

No unsafe credential workaround, DOCX, chunking, raw provider payload storage
or OpenWebUI core patch was introduced.

## 2. Per-Gate Reports

| Gate | Report | Verdict |
| --- | --- | --- |
| Gate 2.5 | `docs/reports/2026-07-02/STT_V2_GATE_2_5_TARGET_RUNTIME_PROOF.report.md` | Pass |
| Gate 3 | `docs/reports/2026-07-02/STT_V2_GATE_3_PROMPT_CATALOG_PROOF.report.md` | Pass |
| Gate 4 | `docs/reports/2026-07-02/STT_V2_GATE_4_QUICK_ACTIONS_PROOF.report.md` | Pass |
| Gate 5 | `docs/reports/2026-07-02/STT_V2_GATE_5_PROMPT_ACCESS_VERSION_PROOF.report.md` | Pass |

## 3. Runtime Status

```text
openwebui_health=healthy running
stage2_status=running
external=200 text/html; charset=utf-8
stage2_image=sha256:44e81ffc1eeb676ae3f4bbfe018627d518dd19a80940d42db8089e4998a0f60e
loader_hash=314c469ae2d9d682419ab35b392559e8901dfaf667740da3f41194649df30d85
action_content_hash=24b97d75d43133d1790caf694f42fea92820cd87cc016bad22e5f1627b899295
```

Safe effective post-processing config:

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

## 4. Implemented Scope

Implemented:

- `TranscriptResultV1` preservation through sidecar artifact store;
- SQLite `ArtifactStoreAdapter` and transcript store path;
- target runtime diarization proof from Gate 2.5;
- OpenWebUI Prompt-backed catalog through `PromptCatalogAdapter`;
- `PostProcessingTemplateV1`, `PostProcessingRequestV1`,
  `PostProcessingResultV1`;
- post-processing executor factory and OpenAI-compatible executor;
- provider egress parity for `stage2-stt` through compose proxy env;
- internal sidecar routes for template list/resolve/execute;
- native OpenWebUI Action operations for template list and execute;
- static loader quick-action buttons and safe-to-fail behavior;
- explicit single-pass long transcript refusal;
- prompt access, version/hash and deleted/missing prompt behavior proofs.

Not implemented by design:

- DOCX export;
- chunking/map-reduce;
- public URL/object-storage provider upload path;
- separate Meetings app or transcript history UI;
- CRM/task tracker integration;
- OpenWebUI core patch.

## 5. Target Runtime Backups And Archives

Deployment/source archives:

```text
Gate 2.5 archive SHA256: 4ca291d02539d6357e5c3ca27828bcafe32badd9ba0e1276381670f01ba07055
Gate 3 archive SHA256: fdb1f3f2c8ef5d87c089dbbe4f5956727a8c13be0f7d29642963fb2eea73ffd0
Gate 4 archive SHA256: 71f7810c16734bae4d9cd1866b67dc07311d7dedb6dfff8e741df2c684b541a0
```

Server backups:

```text
/opt/backups/openwebui-prd0/codex-stt-v2/stt-v2-gate25-server-before-20260702T112423Z.tar.gz
/opt/backups/openwebui-prd0/codex-stt-v2/stt-v2-gate3b-server-before-20260702T114535Z.tar.gz
/opt/backups/openwebui-prd0/codex-stt-v2/stt-v2-gate4-server-before-20260702T115147Z.tar.gz
/opt/backups/openwebui-prd0/codex-stt-v2/openwebui.compose.yml.before-stage2-proxy-20260702T1220PROXY
/app/backend/data/runtime-backups/webui-before-stt-v2-gate4-action-20260702T115147Z.db
/app/backend/data/runtime-backups/webui-before-stt-v2-gate5-prompt-proof-20260702T120000Z.db
/app/backend/data/runtime-backups/webui-before-stt-v2-gate5-success-proof-20260702T1225Z.db
```

## 6. Target Runtime Proof Highlights

Gate 4 successful sidecar execution:

```json
{
  "direct_provider_status": 200,
  "template_count": 2,
  "artifact_type_counts": {
    "post_processing_result": 2,
    "prepared_audio": 1,
    "source_file": 1,
    "stt_job": 1,
    "transcript_result": 1
  },
  "stored_secret_markers_found": false
}
```

Gate 4 Action bridge:

```json
{
  "execute_has_result_ref": true,
  "execute_safe_failure": false,
  "secret_markers_found": false,
  "template_commands": [
    "stt-summary",
    "stt-meeting-protocol"
  ],
  "templates_count": 2
}
```

Gate 5 old-result preservation:

```json
{
  "first_kept_old_hash": true,
  "first_kept_old_version": true,
  "first_stored_version": "gate5-success-v1",
  "second_version": "gate5-success-v2",
  "secret_markers_found": false
}
```

## 7. Validation Commands

Local validation:

```text
python -m pytest -q services/stage2-stt/tests/test_openwebui_action.py
result: 9 passed in 0.56s

python -m pytest -q services/stage2-stt/tests/test_prompt_catalog.py services/stage2-stt/tests/test_post_processing.py services/stage2-stt/tests/test_post_processing_routes.py
result: 16 passed in 2.04s

python -m pytest -q services/stage2-stt/tests
result: 64 passed in 3.46s

node --check deploy/openwebui-static/loader.js
result: pass

git diff --check -- . ':!services/stage2-stt/build'
result: only LF-to-CRLF warnings from Git on Windows
```

Target runtime validation included:

- `docker compose --env-file .env -f compose/openwebui.compose.yml config --quiet`;
- `docker compose --env-file .env -f compose/openwebui.compose.yml build stage2-stt`;
- `docker compose --env-file .env -f compose/openwebui.compose.yml up -d --force-recreate stage2-stt`;
- `docker compose --env-file .env -f compose/openwebui.compose.yml up -d --force-recreate openwebui`;
- internal sidecar probes for capabilities, prompt catalog, post-processing
  execution and long transcript refusal;
- OpenWebUI Action execution from installed `function` table;
- external health check for `https://gpt.alpha-soft.ru/`.

## 8. Acceptance Summary

| Area | Status | Notes |
| --- | --- | --- |
| target Gate 1-2 runtime delivery | Pass | transcript refs, artifact store and diarization proven |
| OpenWebUI Prompts as catalog | Pass | two MVP prompts seeded and resolved |
| prompt body not duplicated in code/config/loader | Pass | prompt bodies stay in OpenWebUI DB |
| quick-action list bridge | Pass | loader and Action route expose two templates |
| quick-action successful LLM execution | Pass | target provider status 200 and two successful executions |
| post-processing result storage | Pass | target `post_processing_result` artifacts stored |
| long transcript behavior | Pass | 413 `transcript_too_long_single_pass`, no chunking |
| prompt access/deleted/change behavior | Pass | target proofs plus local tests |
| old result hash preservation | Pass | target v1/v2 proof |
| no raw LemonFox JSON in prompt/chat/storage | Pass | normalized contract only |
| no secrets in reports/artifacts | Pass | probes redacted and scanned for markers |
| ordinary OpenWebUI chat health | Pass | OpenWebUI healthy and external 200 |
| OpenWebUI core patch avoided | Pass | Action/static loader/sidecar only |

## 9. Known Limitations

- Authenticated Playwright/browser-click proof was not completed; runtime loader
  hash, Action DB execution and sidecar probes cover the current bridge.
- Prompt catalog uses read-only SQLite access to OpenWebUI DB behind an adapter.
  This is update-safe enough for the extension layer, but an official OpenWebUI
  prompt API adapter would be preferable if a stable API becomes available.

## 10. Recommended Next Step

Do not expand into DOCX or chunking yet. The next practical step is a narrow
authenticated browser proof for the quick-action buttons, then operator
documentation for maintaining `OPENWEBUI_OUTBOUND_PROXY` parity across
OpenWebUI and `stage2-stt`.
