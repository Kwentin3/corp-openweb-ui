# STT v2 Native Prompt Quick Action Implementation Proof

Status: implemented locally; runtime deployment proof pending.

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

Pending.
