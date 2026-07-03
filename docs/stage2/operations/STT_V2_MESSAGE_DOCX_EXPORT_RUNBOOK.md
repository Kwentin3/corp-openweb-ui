# STT v2 Message-Level DOCX Export Runbook

Status: MVP operator runbook with semantic formatting notes.

Date: 2026-07-03.

## 1. What This Feature Does

Message-level DOCX export adds a DOCX button under completed assistant messages
in OpenWebUI. A click exports only that selected assistant message.

Current runtime behavior uses `semantic_chat_v1` when the loader can send a
structured source. Source precedence is canonical OpenWebUI message markdown
first, sanitized selected-message HTML second, and plain text as the final
compatibility fallback. Semantic export preserves document structure visible in
chat: headings, paragraphs, lists, tables, blockquotes, links and code blocks.

It does not export:

- the whole chat;
- user messages;
- streaming messages;
- attachments/images/tool artifacts;
- raw provider payloads;
- hidden prompts or internal config.

It is not expected to clone OpenWebUI CSS pixel-for-pixel. Semantic parity is the
goal: the DOCX should remain readable and structurally equivalent to the visible
message.

## 2. Runtime Components

```text
deploy/openwebui-static/loader.js
  injects the DOCX button and handles browser download

openwebui_actions/stage2_media_transcription_action.py
  acts as the OpenWebUI Action bridge

stage2_stt.app
  exposes POST /stage2-api/message-docx/exports

stage2_stt.message_docx
  generates DOCX through python-docx and scans the generated package
```

## 3. Env

Server-side defaults:

```text
STAGE2_STT_MESSAGE_DOCX_MAX_MESSAGE_CHARS=100000
STAGE2_STT_MESSAGE_DOCX_MAX_DOCX_MB=5
```

Internal auth still uses the existing:

```text
STAGE2_STT_INTERNAL_API_KEY
```

Do not expose internal tokens to the browser.

## 4. Deploy Checklist

1. Pull the target commit on the server.
2. Rebuild and recreate the `stage2-stt` service so `python-docx` is installed.
3. Restart or recreate OpenWebUI if needed so the mounted static loader is fresh.
4. Update the stored OpenWebUI Action function content from
   `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`.
5. Verify external HTTPS still returns 200.
6. Verify sidecar DOCX endpoint from inside the Docker network.
7. Verify a browser export manually when an authenticated browser session is
   available.

Typical compose command:

```text
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --build stage2-stt
docker compose --env-file .env -f compose/openwebui.compose.yml restart openwebui
```

The exact Action update command depends on the runtime DB/admin procedure already
used for STT v2 Action updates.

## 5. Local Verification

```text
python -m pip install -e "services/stage2-stt[test]"
python -m pytest -q services/stage2-stt/tests
python -m compileall -q services/stage2-stt
node --check deploy/openwebui-static/loader.js
```

Expected current local result:

```text
100 passed
```

## 6. Manual Browser Proof

Use a normal authenticated OpenWebUI session.

1. Generate an ordinary assistant answer.
2. Confirm a DOCX button appears under the completed assistant message.
3. Confirm no DOCX button appears under user messages.
4. Click DOCX.
5. Confirm the browser save/download flow starts.
6. Open the DOCX in Word, LibreOffice or `python-docx`.
7. Confirm the DOCX contains only the selected assistant message.
8. Confirm previous/next chat messages and toolbar labels are absent.
9. Repeat for an STT transcript assistant message.
10. Repeat for an STT post-processing result message.

When `semantic_chat_v1` is active, rich formatting should be preserved as
document semantics. If only `simple_mvp` fallback is used, rich formatting may be
simplified and the result should carry a typed degradation warning.

Additional proof for `semantic_chat_v1` rollout:

1. Generate an assistant message containing headings, paragraphs, nested lists,
   a markdown table, a blockquote, a link and a fenced code block.
2. Export the message to DOCX.
3. Open the DOCX in Word, LibreOffice or `python-docx`.
4. Confirm tables remain tables, lists remain lists, links remain links and code
   remains a monospace block.
5. Confirm content after a markdown horizontal rule is still present, especially
   markdown tables and any following paragraphs.
6. Confirm no toolbar controls, hidden config, raw HTML, script/style/event
   handlers, prompt bodies, provider payloads or internal URLs are present.
7. Repeat on a plain-text-only message and confirm a typed degradation warning or
   typed refusal, depending on the selected fallback mode.

## 7. Failure Handling

Expected typed refusals:

```text
message_docx_empty_message
message_docx_message_too_large
message_docx_no_safe_source
message_docx_no_leak_check_failed
message_docx_generation_failed
message_docx_access_denied
```

Failure must not append noisy diagnostic content into chat. The loader uses the
DOCX button state and tooltip for local feedback.

## 8. No-Leak Spot Check

After a generated DOCX is available:

1. Unzip the `.docx`.
2. Inspect at least:

```text
word/document.xml
docProps/core.xml
docProps/app.xml
word/_rels/document.xml.rels
_rels/.rels
```

3. Confirm no provider payload markers, prompt bodies, tokens, cookies, internal
   sidecar URLs, previous/next message sentinels or toolbar labels are present.

## 9. Rollback

If the feature causes runtime issues:

1. Restore the previous `loader.js` from Git or server backup.
2. Restore the previous OpenWebUI Action function content.
3. Recreate/restart OpenWebUI.
4. If sidecar rebuild is the suspected cause, redeploy the previous commit for
   `stage2-stt`.

Normal chat and STT transcription should remain available because DOCX export is
an additive operation behind the loader and Action bridge.
