# STT v2 MVP Operator Notes

Status: pilot-readiness operator notes.

Date: 2026-07-02.

Scope: current STT v2 MVP post-processing contour only. DOCX, chunking,
OpenWebUI Prompt API Adapter, extra prompt templates and separate transcript UI
are out of scope.

## Runtime Ownership

`stage2-stt` is the sidecar service in the production OpenWebUI compose stack.
It owns:

- STT provider adapter calls;
- normalized `TranscriptResultV1`;
- SQLite ArtifactStore records;
- transcript lookup by opaque `transcript_ref`;
- prompt catalog access through the accepted MVP `openwebui_sqlite` adapter;
- render-only native chat prompt drafts for transcript quick actions;
- server-side post-processing execution as a compatibility/fallback path;
- typed long-transcript refusal.

OpenWebUI owns:

- chat UX;
- uploaded file UX;
- native Action function;
- static loader helper;
- native Prompt rows used as template source of truth.

OpenWebUI core must not be patched for this MVP.

## Important Env

Expected MVP shape:

```text
STAGE2_STT_ARTIFACT_STORE_MODE=sqlite
STAGE2_STT_PROMPT_CATALOG_MODE=openwebui_sqlite
STAGE2_STT_POSTPROCESSING_EXECUTOR_MODE=openai_compatible
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true
STAGE2_STT_POSTPROCESSING_MAX_TRANSCRIPT_CHARS=60000
```

Secrets must exist server-side but must not be printed:

```text
STAGE2_STT_INTERNAL_API_KEY
STAGE2_LEMONFOX_API_KEY
STAGE2_STT_POSTPROCESSING_OPENAI_API_KEY
```

Provider egress parity matters. The effective outbound proxy and no-proxy
settings must stay synchronized between OpenWebUI and `stage2-stt`. If one
container has working provider egress and the other does not, post-processing
can fail even while OpenWebUI itself is healthy.

## Checks

Use sanitized checks only. Do not paste token values, full provider responses,
prompt bodies or raw provider payloads into reports or tickets.

Capabilities check:

- call the sidecar capabilities route from inside the `stage2-stt` container;
- expected: provider `lemonfox`, adapter `lemonfox`,
  `artifact_store_mode=sqlite`, `artifact_store_available=true`,
  `supports_speaker_labels=true`.

Prompt catalog check:

- call the sidecar post-processing template list route with internal auth;
- expected two templates:
  - `stage2.stt.summary.v1` / `stt-summary`;
  - `stage2.stt.meeting_protocol.v1` / `stt-meeting-protocol`;
- metadata must include hash/version, not prompt body.

Quick-action bridge check:

- execute installed OpenWebUI Action operation `list_postprocessing_templates`;
- expected two template commands and no prompt body in the returned payload.

Native prompt draft check:

- execute installed OpenWebUI Action operation `draft_postprocessing_prompt`
  against a valid recent `transcript_ref` and its full artifact context;
- expected empty `content`, a `stage2_stt_prompt_draft.prompt_text` value,
  prompt hash/version metadata and no secret/raw-provider markers.

Server-side post-processing fallback check:

- execute `execute_postprocessing` only when the compatibility path is being
  verified;
- expected status 200, `result_ref` prefix `art_`, prompt hash length 64 and
  no secret/raw-provider markers in Action output.

Provider egress check:

- use a low-cost authenticated provider connectivity probe from `stage2-stt`;
- expected provider HTTP status 200;
- if it fails while OpenWebUI egress works, compare effective proxy/no-proxy env
  between the two containers.

## Safe Restart

From the production compose directory:

```text
docker compose --env-file .env -f compose/openwebui.compose.yml config --quiet
docker compose --env-file .env -f compose/openwebui.compose.yml up -d --force-recreate stage2-stt
```

Restarting `stage2-stt` should not require an OpenWebUI core patch. Recreate
OpenWebUI only when the Action/static loader mount or OpenWebUI runtime itself
needs it.

## Logs

Look at recent logs only, and scan for markers before sharing excerpts:

```text
docker logs --since 30m stage2-stt
docker logs --since 30m openwebui
```

Do not share logs containing:

- API keys or token values;
- `Authorization` headers;
- raw LemonFox/provider payloads;
- hidden config or secrets.

## Failure Signals

Provider egress is likely broken when:

- server-side fallback post-processing returns provider/executor failure;
- direct provider connectivity from `stage2-stt` fails;
- OpenWebUI has proxy/no-proxy env but `stage2-stt` does not.

Prompt catalog is likely broken when:

- template list returns zero templates;
- template metadata lacks hash/version;
- `STAGE2_STT_PROMPT_CATALOG_MODE` is not `openwebui_sqlite`;
- sidecar cannot read the OpenWebUI prompt DB mount.

ArtifactStore is likely broken when:

- `artifact_store_available=false`;
- `transcript_ref` is absent after transcription;
- prompt draft or post-processing fails with artifact access or scope errors.

## MVP Limitations

- Message-level DOCX export is implemented separately; specialized structured
  post-processing DOCX export is not part of this MVP note.
- Chunking/map-reduce is not implemented.
- Long transcripts receive safe refusal instead of silent truncation.
- OpenWebUI Prompt API Adapter is deferred.
- SQLite PromptCatalogAdapter is accepted as MVP/default.
- Only two MVP templates are included.
- No separate Meetings app exists.
- No separate transcript history UI exists.
