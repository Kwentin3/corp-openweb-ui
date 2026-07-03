# STT v2 Manual Browser Test Program

Status: controlled pilot manual test program.

Date: 2026-07-02.

Audience: user or operator testing in the production browser UI.

Do not use sensitive customer media for the first pass. Use a short, harmless
audio sample.

## Test Record

```text
Tester:
Date:
Browser:
OpenWebUI account:
Input file name:
Input file duration:
Result: PASS / FAIL
Notes:
Screenshots saved safely: yes / no
```

Screenshots are optional. If used, avoid showing secrets, private customer data
or unrelated chat content.

## 1. Login And New Chat

1. Open the production OpenWebUI in a browser.
2. Log in normally.
3. Create a new chat.
4. Confirm the normal chat composer is usable.

Expected:

- OpenWebUI loads without errors.
- A new chat can be created.
- Normal chat controls remain visible.

## 2. Upload Short Audio

1. Attach a short audio file.
2. Use a small, non-sensitive sample.
3. Start the STT transcription action.

Expected:

- The upload completes.
- STT action starts without breaking the chat.
- Progress/status messages are understandable.

## 3. Transcript Result

1. Wait for transcription to finish.
2. Confirm the answer appears in the same chat.
3. Confirm the visible output starts with `Transcript:`.
4. Confirm a `Transcript reference` is present when artifact storage succeeds.
5. If provider speaker labels are present, confirm the raw transcript is
   grouped into readable generic speaker turns such as `Спикер 1` / `Спикер 2`.

Expected:

- Transcript text is visible in the same chat.
- The old flat transcript output still works when speaker labels are absent.
- Speaker-labeled output uses generic labels only; it does not infer real
  participant names.
- No raw provider JSON is visible.
- No debug headers, tokens or API keys are visible.

## 4. Quick Action List

1. After the transcript appears, check that transcript quick actions are visible.
2. Confirm these two actions are available:
   - `Краткий пересказ`;
   - `Протокол встречи`.

Expected:

- The actions are visible near the transcript workflow.
- No prompt body is shown to the user.
- If quick actions are not visible, record it as a UI issue and continue with
  server-side bridge evidence from the closeout report.

## 5. Short Summary

1. Click `Краткий пересказ`.
2. Wait for completion.
3. Confirm the processed result appears in the same chat.

Expected:

- The result is readable.
- The result is returned in the same OpenWebUI chat.
- A post-processing result reference is visible.
- No prompt body, raw provider JSON, token or debug payload is visible.

## 6. Meeting Protocol

1. Click `Протокол встречи`.
2. Wait for completion.
3. Confirm the processed result appears in the same chat.

Expected:

- The result is readable.
- The result is returned in the same OpenWebUI chat.
- A post-processing result reference is visible.
- No prompt body, raw provider JSON, token or debug payload is visible.

## 7. Long Transcript Behavior

Only run this if a safe non-sensitive long transcript test sample is available.
Do not use private customer recordings for this check.

Expected:

- The current MVP must refuse overly long single-pass post-processing safely.
- It must not silently truncate the transcript.
- It must not start DOCX export or chunking.

If no safe long sample is available, mark this block as:

```text
NOT_RUN_SAFE_SAMPLE_UNAVAILABLE
```

The closeout report contains the target-runtime refusal proof for the MVP policy.

## 8. No-Leak Visual Check

In the visible chat output, confirm absence of:

- raw LemonFox/provider JSON;
- request/response headers;
- API keys, tokens or cookies;
- prompt bodies;
- full rendered prompt;
- internal service URLs.

Expected:

- User-visible output contains only transcript text, processed result text,
  safe references and human-readable warnings.

## 9. Pass/Fail Criteria

Mark the browser test `PASS` if:

- login and new chat work;
- upload and transcription work;
- transcript appears in the same chat;
- speaker-labeled transcripts are readable when labels are available, with flat
  fallback otherwise;
- both quick actions are visible;
- both quick actions return results in the same chat;
- no raw provider/debug/secret content is visible.

Mark `FAIL` if:

- OpenWebUI is unavailable;
- transcription cannot start;
- transcript never appears;
- both quick actions are missing;
- a quick action fails repeatedly;
- secrets, raw provider payloads or prompt bodies are visible.
