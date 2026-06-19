# OpenWebUI STT Playwright UI Proof Report

Date: 2026-06-19
Status: browser UI proof completed with local shell-driven Playwright
Final verdict: `action_runtime_works_small_frontend_patch_needed`

## 1. Summary

The prepared-MP3 runtime path remains technically proven through the OpenWebUI
Action API, but the current visible OpenWebUI chat UI is not acceptable as the
prepared-MP3 MVP UX.

Playwright proved:

- admin login works in the real browser UI;
- new chat UI loads;
- MP3 upload through the chat composer works with a sanitized filename;
- the attachment is visible in the composer and in the sent chat context;
- OpenWebUI's normal upload path also shows a confusing built-in processing
  error for the MP3;
- no visible `Transcribe` / `Transcription` / `Транскрибировать` Action
  affordance appears near the attachment, in composer menus, integration menu,
  controls, or message menus;
- browser network did not call `/api/chat/actions/...`;
- no transcript appeared through the browser/chat UI path.

Therefore the Action runtime is usable as a backend integration contract, but
the current native Action UX is not discoverable/executable enough for the
prepared-MP3 MVP without a small frontend patch.

## 2. Runtime baseline

Baseline from the previous report:

```text
OpenWebUI upload/API path -> Action -> stage2-stt sidecar -> Lemonfox -> transcript
```

Current server baseline rechecked before the UI proof:

```text
openwebui: running, healthy
stage2-stt: running, no public host port
traefik: running
OpenWebUI -> stage2-stt capabilities: OK
Action active=True
Action global=False
Action valves configured with sidecar URL and internal token
```

No runtime config was changed in this task.

## 3. Playwright environment

Mode:

```text
local shell-driven Playwright
```

Reason: built-in `mcp__playwright__browser_*` tools were not available in this
environment.

Execution details:

```text
Node.js: v22.19.0
Playwright installed under ignored local/playwright-ui-proof/
Browser: system Chrome
Target: https://gpt.alpha-soft.ru/
```

Temporary Playwright runner files are under ignored `local/` and were not
staged.

## 4. Login proof

Evidence:

```text
playwright_login_worked=true
initial_url=https://gpt.alpha-soft.ru/auth?redirect=%2F
post_login_url=https://gpt.alpha-soft.ru/
title=Alpha Soft AI Chat (Open WebUI)
chat_shell_visible=true
composer_visible=true
file_inputs=2
```

Credentials were read from ignored `.env`; password and tokens were not printed
or written to report artifacts.

## 5. Upload proof

The approved local MP3 was uploaded through the real chat composer using a
sanitized browser filename.

Evidence:

```text
strict_upload_status=200
strict_attachment_visible=true
strict_upload_processing_error=true
file_id_present=true
filename_sanitized=true
```

The visible attachment filename used in the proof was:

```text
proof-media.mp3
```

The original local filename was not written to this report or screenshots.

Important UX finding: the standard OpenWebUI file upload path showed a visible
toast:

```text
'NoneType' object is not subscriptable
```

This is not a Stage 2 sidecar error. It appears to come from OpenWebUI's normal
file-processing path for the uploaded MP3 and is confusing for users.

## 6. Action discovery UX

Checked surfaces:

- composer attachment card;
- composer `More` / `Больше` menu;
- `Integrations` / `Интеграции` menu;
- `Controls`;
- sent message area;
- visible post-send menus matching `More` / `Больше`.

Strict discovery evidence:

```text
strict_action_text_after_upload=false
strict_action_text_after_send=false
strict_menus_before_with_action=0
strict_menus_after_with_action=0
strict_api_chat_actions_called=false
```

The first exploratory run initially matched `stage2` in the sanitized filename,
so a second strict run used `proof-media.mp3` and searched only for
`Transcribe`, `Transcription`, and `Транскриб`. That strict run found no visible
Action affordance.

UX result:

```text
No user-discoverable Transcribe action exists in the tested OpenWebUI chat UI.
```

## 7. Action execution proof

Browser UI execution did not occur because no visible Action control was found.

Evidence:

```text
strict_api_chat_actions_called=false
playwright_transcript_marker_visible=false
```

The previous API proof remains valid, but it is not browser UI proof:

```text
POST /api/chat/actions/stage2_media_transcription_action -> transcript returned
```

## 8. Transcript placement proof

Transcript placement in the visible browser chat was not proven.

Evidence:

```text
playwright_transcript_marker_visible=false
strict_api_chat_actions_called=false
```

The browser chat showed the ordinary OpenWebUI file/chat workflow, not the Stage
2 Action result. No transcript text was captured or committed.

## 9. Progress/error/cancel UX

Current UI state coverage:

| State | Status | Evidence |
| --- | --- | --- |
| Login | Pass | Browser login and chat shell loaded. |
| Uploading/uploaded | Partial | Attachment appears, but OpenWebUI emits a confusing processing error. |
| Ready to transcribe | Fail | No visible Transcribe action. |
| Busy/progress | Not proven | Action was not executable from UI. |
| Completed transcript | Not proven | No Action result in chat UI. |
| Failed transcript | Not proven | No Action execution path. |
| Cancel | Not proven | No visible Action/job progress surface. |

UI integrity status: fail for MVP prepared-MP3 transcription UX.

Violations:

- primary user action is not visible;
- upload error feedback is confusing and not tied to the STT Action;
- no Action busy/progress/terminal state is available from the tested UI;
- keyboard/focus operation for the transcription action cannot be assessed
  because the control is absent.

## 10. Browser normalization assessment

Browser ffmpeg.wasm normalization is not implementable through the current
server-side Action UI alone.

Assessment:

- OpenWebUI Action code runs server-side;
- the current visible UI does not expose attachment-level Transcribe;
- browser-side ffmpeg.wasm needs a frontend integration point at or near the
  media attachment/composer;
- prepared MP3 can remain the MVP input once a visible Action button exists;
- source media/video normalization should be a follow-up slice after the
  prepared-MP3 UI affordance is fixed.

## 11. Security/no-secret checks

Controls:

- admin password and session token were not printed;
- Lemonfox key was not exposed;
- `stage2-stt` remained private;
- screenshots contain sanitized filenames only;
- no transcript text was printed or committed;
- original audio filename was not written to the report;
- test upload file was deleted through OpenWebUI API;
- test chat was deleted through OpenWebUI API;
- local MP3 remains ignored and uncommitted.

Cleanup evidence:

```text
strict_cleanup_file_delete_status=200
strict_cleanup_chat_delete_status=200
```

## 12. Screenshots/evidence

Safe evidence directory:

```text
docs/reports/2026-06-19/openwebui-stt-playwright-ui-proof/
```

Files:

```text
01-after-login.png
02-after-upload.png
03-more-menu-after-upload.png
04-after-send-or-action-search.png
ui-proof-evidence.json
action-discovery-strict.json
```

Notes:

- screenshots show sanitized filenames only;
- no transcript is present;
- `02-after-upload.png` captures the upload plus OpenWebUI processing error;
- `03-more-menu-after-upload.png` captures the attachment menu without a
  Transcribe action.

## 13. UX verdict

Verdict:

```text
action_runtime_works_small_frontend_patch_needed
```

Reason:

- the Action runtime and sidecar path work through API;
- the real browser UI upload works;
- the real browser UI does not expose the Action in a discoverable attachment
  workflow;
- transcript return into visible chat UI is not proven because the Action cannot
  be triggered from the tested UI.

Native Action UX as currently exposed is not acceptable for the prepared-MP3
MVP.

## 14. Recommended next slice

Implement a thin, upgrade-conscious frontend patch:

1. Show `Транскрибировать` on supported audio/video attachment cards.
2. Start with prepared MP3 support.
3. Call the existing OpenWebUI Action endpoint or a thin OpenWebUI backend shim
   that reuses the existing Action/sidecar contract.
4. Surface explicit states: ready, busy, completed, failed, cancel requested.
5. Keep Lemonfox/provider behavior out of the UI.
6. Keep `stage2-stt` private.
7. Add browser ffmpeg.wasm normalization only after the prepared-MP3 affordance
   is proven.

Companion plan:

```text
docs/stage2/implementation/STT_FRONTEND_MEDIA_ACTION_PATCH_PLAN.md
```

## 15. Final verdict

```text
action_runtime_works_small_frontend_patch_needed
```

The prepared-MP3 backend/runtime path is proven, but the real OpenWebUI browser
UX needs a small frontend patch before the MVP can be considered user-ready.
