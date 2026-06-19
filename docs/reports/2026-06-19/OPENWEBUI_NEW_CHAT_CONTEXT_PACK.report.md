# OpenWebUI New Chat Context Pack Report

## 1. Summary

Created a compact, copyable Stage 2 / STT / OpenWebUI context pack for moving
the work into a new chat without re-reading the full history.

Output:

- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`

The pack records the current STT MVP status as
`implemented/proven/current-stage closed`, summarizes the extension-first
implementation pattern, preserves the no-separate-GUI boundary, and points the
next agent to the active hardening backlog.

## 2. Sources read

Living docs read or inspected:

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`

Implementation/config files inspected:

- `deploy/openwebui-static/loader.js`
- `deploy/openwebui-static/stage2-stt-normalization.json`
- `scripts/fetch-ffmpeg-wasm-assets.sh`
- `compose/openwebui.compose.yml`
- `services/stage2-stt/stage2_stt/`
- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`
- `services/stage2-stt/tests/`

Reports read or inspected:

- `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_FRONTEND_MEDIA_ACTION_PATCH.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_BACKEND_IMPLEMENTATION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_DOCS_IMPLEMENTATION_DRIFT_AUDIT.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_SIDECAR_ROUTING_AUTH_AUDIT.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_NATIVE_STT_UX_INTEGRATION_RESEARCH.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_MEDIA_ATTACHMENT_STT_ACTION_REFINE.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_MEDIA_ATTACHMENT_STT_IMPLEMENTATION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_INPUT_FORMAT_CONTRACT_REFINE.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_BACKEND_IMPLEMENTATION_PLAN.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_NATIVE_WEB_STT_RECORDER_PATCH.report.md`

Historical reports were used as sources only; no historical report was edited.

## 3. Context pack created

Created:

- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`

Structure included:

- one-screen summary;
- implemented/proven scope;
- current architecture diagram and responsibilities;
- extension-first implementation pattern;
- key architectural decisions;
- important pitfalls / do not reopen;
- current limitations / hardening backlog;
- suggested next work;
- key files for a future agent;
- how to talk to the next chat;
- copy-paste compact context.

## 4. Key facts included

Included:

- STT MVP is `implemented/proven/current-stage closed`;
- current path is OpenWebUI attachment -> static loader -> browser
  normalization -> Action Function -> private sidecar -> Lemonfox adapter ->
  transcript in OpenWebUI UX;
- extension-first pattern is the preferred implementation model;
- no separate user-facing STT GUI exists or is planned for MVP;
- no browser-to-provider path and no browser provider secret;
- input compatibility is ffmpeg.wasm capability-based, not a universal media
  promise;
- current browser output profile is `mp3_high_compat`;
- Opus remains pending provider/path proof before default;
- prepared-audio storage is policy/config driven through `auto|s3|none`;
- `prepared_audio_storage_transient` should be presented as a human warning
  that prepared audio is not durably saved at the MVP stage;
- native OpenWebUI microphone dictation is separate from attachment-level
  `Transcribe`;
- hardening backlog and next suggested work are explicit.

## 5. Secrets/sensitive data excluded

Excluded:

- provider secret values;
- internal sidecar token values;
- admin credentials;
- SSH connection details;
- private key material;
- runtime env-file contents;
- transcript content;
- sensitive source media filenames;
- customer media contents;
- host/IP-specific deployment details not needed by a future coding agent.

The pack contains repo-local paths and architectural facts only.

## 6. Recommended use in new chat

In a new chat, paste the `Copy-paste compact context` section or ask the next
agent to read:

```text
docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md
```

Then give only the next bounded task, for example:

```text
Continue from the Stage 2 STT hardening backlog. Do not re-plan STT from zero,
do not add a separate STT GUI, and do not expose provider secrets in browser.
```

## 7. Final verdict

```text
new_chat_context_pack_ready
```
