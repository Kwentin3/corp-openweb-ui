# STT v2 Native Prompt Quick Action Implementation Proof

Status: implemented, pushed and deployed to PRD-0; manual authenticated browser
click proof pending.

Date: 2026-07-03.

## 1. Summary

Quick actions were refactored from hidden server-side post-processing result
insertion to native OpenWebUI prompt submission.

Previous flow:

```text
quick action click
-> sidecar executes selected prompt server-side
-> processed result is returned as Action content
-> loader appends processed result into the current composer/message draft
```

New flow:

```text
quick action click
-> Action asks sidecar for PostProcessingPromptDraftV1
-> sidecar resolves OpenWebUI Prompt and normalized TranscriptResultV1
-> sidecar returns rendered prompt_text
-> loader places prompt_text into the normal OpenWebUI composer
-> loader clicks the native send control when it is safely found
-> the LLM answer appears as a normal assistant message
```

OpenWebUI core remains unpatched.

## 2. Contract Changes

Added render-only contracts:

```text
PostProcessingPromptDraftRequestV1
PostProcessingPromptDraftV1
```

`PostProcessingPromptDraftV1` is not a processed result and does not create a
`result_ref`. It contains the visible `prompt_text` intended for native
OpenWebUI chat submission.

The existing `PostProcessingRequestV1` and `PostProcessingResultV1` remain for
the server-side compatibility/fallback path.

## 3. Runtime Surface

Sidecar:

```text
POST /stage2-api/transcription/post-processing/prompt-draft
```

OpenWebUI Action operation:

```text
stage2_stt.operation=draft_postprocessing_prompt
```

Static loader:

- quick action requests `stage2_stt_prompt_draft`;
- quick action no longer calls `execute_postprocessing`;
- quick action no longer appends processed result content;
- loader refuses to overwrite an unrelated composer draft;
- if native send cannot be found, the prompt remains visible in composer with
  explicit status instead of silently falling back.

## 4. Preservation Rules

Preserved:

- OpenWebUI core is not patched;
- raw LemonFox/provider JSON is not exposed;
- prompt bodies are not included in the quick-action list payload;
- prompt rendering uses normalized transcript projection only;
- artifact access and prompt access checks are shared with server-side
  post-processing execution;
- the same prepared OpenWebUI file id is used for transcript access.

## 5. Local Verification

Commands were run from:

```text
D:\Users\Roman\Desktop\Проекты\corp-openweb ui
shell=powershell
```

Targeted implementation tests:

```text
python -m pytest -q services/stage2-stt/tests/test_post_processing.py services/stage2-stt/tests/test_post_processing_routes.py services/stage2-stt/tests/test_openwebui_action.py services/stage2-stt/tests/test_loader_static.py
36 passed in 2.19s
```

Full sidecar suite:

```text
python -m pytest -q services/stage2-stt/tests
93 passed in 3.31s
```

Syntax and compile checks:

```text
python -m compileall -q services/stage2-stt
pass

node --check deploy/openwebui-static/loader.js
pass

git diff --check
pass
```

Closed-world checks:

```text
rg workspace/path/secret patterns in services/stage2-stt and loader
no matches

python -m pip wheel --no-deps --wheel-dir %TEMP% services/stage2-stt
Successfully built openwebui-stage2-stt

wheel contains:
stage2_stt/app.py=True
stage2_stt/post_processing.py=True
stage2_stt/contracts.py=True
openwebui_actions/stage2_media_transcription_action.py=True
```

Factory anti-drift anchors:

```text
PostProcessingExecutorFactory.create anchor covered
FORBIDDEN direct OpenAI-compatible route anchor covered
```

## 6. Runtime Deployment

Implementation commit:

```text
75bf0e3 feat: submit stt quick actions as native prompts
```

Server git state:

```text
target=/opt/openwebui-prd0
HEAD=75bf0e3
```

Sidecar build/recreate:

```text
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --build stage2-stt

image_manifest=sha256:4277011d8de9822b493fb10bc9a472c886c97640028ca1eb4b71da7104bded34
image_config=sha256:b3e7f4df7a945c080d1ecd1d1a55beb228cf001fecf274e73c2368b2ecd7b055
container=stage2-stt started
```

OpenWebUI Action DB update:

```text
function_id=stage2_media_transcription_action
rows_updated=1
file_sha256=0dbeb58aa9495ac0013fed2dbf9cd935e9da01bf0118d0da430a1aba30f6ace7
db_sha256=0dbeb58aa9495ac0013fed2dbf9cd935e9da01bf0118d0da430a1aba30f6ace7
has_draft_operation=True
has_prompt_draft_endpoint=True
has_execute_operation=True
backup_dir=/opt/openwebui-prd0/backups/codex-stt-v2/20260703T115241Z-native-prompt-action-db
```

OpenWebUI was force-recreated after the Action DB update to reload the
installed Action and remount the static loader.

Static loader proof:

```text
host_loader_sha256=ae5c6e03a517a9a7e80d36353e79074feb13901d7f2c25e49e5e13ecf4501c65
container_loader_sha256=ae5c6e03a517a9a7e80d36353e79074feb13901d7f2c25e49e5e13ecf4501c65
public_loader_sha256=ae5c6e03a517a9a7e80d36353e79074feb13901d7f2c25e49e5e13ecf4501c65
public_loader_has_draft_operation=True
public_loader_has_native_submit=True
public_loader_uses_execute_postprocessing=False
```

Sidecar runtime proof:

```text
sidecar_has_prompt_draft_route=True
contract_has_prompt_text=True
stage2_capabilities_status=200
capability_keys=adapter_id,artifact_store_available,artifact_store_mode,available_output_profiles,cancel_strategy,declared_input_extensions,declared_input_mime_prefixes,fallback_output_profile
```

Service health:

```text
openwebui: Up / healthy
stage2-stt: Up
https://gpt.alpha-soft.ru/ -> HTTP 200
```

Recent log scan:

```text
stage2-stt started without traceback/error markers.
openwebui restarted healthy. Startup still logs the known read-only static
loader warning because loader.js is bind-mounted read-only; /static/loader.js
is served with HTTP 200.
```

Manual authenticated browser proof still required:

```text
upload audio
run transcription
click a transcript quick action
verify prompt is submitted as a normal user turn
verify the next assistant message contains the model response
verify the raw transcript is not appended with a hidden processed result
```

## 7. Current Verdict

```text
SERVER_SIDE_PASS_BROWSER_MANUAL_PENDING
```
