# OpenWebUI 0.12.2 candidate and cutover

## Authorized outcome

Prepare a second isolated OpenWebUI, connect the existing integrations, qualify
ordinary user workflows, rehearse a current data transfer and rollback, then
switch the portal after acceptance. Keep one production writer and preserve the
old image and data for a bounded rollback. No third permanent WebUI.

The source base is `f6d0a02dea8cbb680a10a7464b7938eb1d69aac9`; the installed
STT current-message fix is restored from PR #559, commit
`c091819e7e7a988519b7dc8ad1760a15d917b891`, whose Function source SHA256
`1109022e0837ece1e624f4d4bffaea5d0a71fa45d6c9948346891a981dc2c89b`
was compared with the running registry. The exact accepted runtime remains the
authority for extension content, valves, grants and integration endpoints.

Candidate upstream is stable `v0.12.2`, commit
`6a18585ff4c2e5f6805f682222cfbc46dc669ef8`. Registry and built-image identities
must be recorded before acceptance; a tag alone is insufficient.

## Acceptance contract

| ID | Required evidence |
| --- | --- |
| R1 | Separate WebUI DB/files/vector data, STT artifacts and Terminal homes; Office callback, STT URL and Terminal connection point to candidate owners. |
| R2 | Native migration succeeds; integrity, users/chats/messages/files/grants, attachment references and retained file hashes match the source snapshot. |
| R3 | Current native connections, model catalog, grants, Functions/Valves, Tools, Skills, Actions and Terminal configuration are preserved. |
| R4 | Ordinary user DOCX/XLSX/PPTX create, render/review/edit, follow-up, download and source preservation; real formula recalculation where applicable. |
| R5 | Native tool order, original user intent, tool images and opaque Responses reasoning survive; CC fallback and model switch remain correct. |
| R6 | Current-message STT, same-ID M4A/MP4 preparation, metadata, transcript and historical attachments work through native UI. |
| R7 | Terminal transfer/publication, search, allowed access and denied cross-user file access work. |
| R8 | Existing production stays available during qualification; measured resource peaks, restart/OOM counters and process lifecycle are acceptable. |
| R9 | Final current-data refresh, migration and route change are rehearsed and timed; exactly one production route/writer is active. |
| R10 | Rollback is tested against the stated write boundary; old images, environment and original volumes remain recoverable. |

Green component tests or a healthy container do not satisfy product acceptance.
Use sequential ordinary-user checks on synthetic documents with known contents;
retain private chat/provider evidence on the host, publishing only safe receipts.

## Isolation and preservation

The candidate Compose is `compose/openwebui.release-0122.compose.yml`.
Its WebUI is bound only to host loopback port 18122 and reached by an SSH tunnel.
Its Traefik labels remain disabled until the route overlay is intentionally used.
Search reuses the existing native service; no parallel search deployment.

Read effective persisted configuration before boot. Disable candidate background
automations and temporarily disable the media Event until the copied storage and
pending markers are verified. Never rely on environment flags alone to override
persisted config. Do not share mutable source SQLite, upload paths or external
storage with the candidate. Copy secrets only into protected host-local files.

Production compaction was confirmed disabled. Preserve this setting: the native
0.12.2 compaction boundary can separate an opaque reasoning carrier from a
retained tool batch. That feature is outside this candidate's accepted behavior.
Stateful Responses remains a separately evaluated provider-specific option;
prompt caching does not require it and cannot repair missing context.

## Cross-provider call ID boundary

The observed Gemini-to-Responses replay fails because a signature-bearing call
ID exceeds the destination's 64-character limit. Direct OpenAI Chat Completions
also rejects the observed 166-character ID; its route is qualified separately.

| Meaning | Existing owner | Representation at the consumer boundary |
| --- | --- | --- |
| Original call ID and Google thought signature | Native persisted chat output and Google/LiteLLM continuation | Keep the original bytes; no history migration or signature cache. |
| Destination API type | Native `get_openai_connection` | Select the existing Responses converter; no model-name or hostname rules. |
| Responses call/result correlation | `convert_to_responses_payload` in the existing context overlay | Keep IDs up to 64 characters; project longer complete pairs to the same full SHA256 hex only in the outgoing request. Refuse collisions or incomplete long pairs. |
| Provider-side response state | Native `previous_response_id` and Stateful Responses flag | Keep the candidate stateless; refuse long-ID projection with `previous_response_id`. Short native IDs retain their existing behavior. |
| Chat Completions signature adaptation | Maintained LiteLLM provider transport | Separate native gateway configuration and route acceptance; this Responses change adds no CC transformation. |

The Responses projection preserves input order, user text, arguments, images,
opaque reasoning and the stored source. It introduces no persistence, client or
tool loop. A successful Responses check alone does not prove every model-switch
route; the return to Gemini must still replay its original signature-bearing ID.

## Repeated full refresh and QA restoration

Each full refresh uses a new phase directory under
`/opt/openwebui-upgrade-0122` and a new `openwebui-0122-<phase>` volume prefix.
Use the full snapshot path, without `--resume-config`.
Keep the original production volumes and the accepted QA phase, including its
three volumes, image ID, protected environment, resolved Compose and runtime
configuration receipts. The shared candidate Compose project must have no
containers before preparation; stop/remove only its containers with the saved
QA Compose composition and `down`, without `-v`. Include the optional Google
overlay in that composition if it was active. Leave production running for the
online rehearsal.

Run the existing host scripts with the qualified immutable image ID in
`qualified_image`. The following example requires an unused phase/root prefix:

```bash
task_root=/opt/openwebui-upgrade-0122
phase_root="$task_root/refresh-rehearsal-01"
volume_prefix=openwebui-0122-refresh-rehearsal-01
python3 "$task_root/prepare_stage.py" --root "$phase_root" --volume-prefix "$volume_prefix"
python3 "$task_root/launch_stage.py" --root "$phase_root" --image "$qualified_image"
```

Launch binds the receipt to that exact phase and approved source container/image
IDs. Its three env selectors must name that phase's owned mode-0600 regular
files without symlinks; ambient shell selectors cannot redirect them or the
three prepared volumes. `webui.env` must omit `WEBUI_BUILD_HASH` and
`WEBUI_BUILD_CHANNEL`, so the qualified image owns its build identity. Only the
original base-root receipt may omit `phase_root`, with all three original
default volumes and the original approved source IDs/images. Existing boot or
launch markers are recovery evidence; do not reset them to force a relaunch.

Wait for native migration and health, then prove **R2 before applying runtime
deltas**:

```bash
python3 "$task_root/verify_migration.py" \
  --source "$phase_root/source-webui.sqlite3" \
  --candidate "/var/lib/docker/volumes/${volume_prefix}_data/_data/webui.db" \
  --receipt "$phase_root/prepared.private.json" \
  --output "$phase_root/migration.private.json"
```

Then replay only accepted configuration through its native owners. Apply
`TASK_MODEL_PARAMS={"custom_params":{"reasoning":{"effort":"none"}}}` using
`POST /api/v1/tasks/config/update`. Verify isolated media callbacks/storage and
pending markers before restoring the source's media Event activation state.
Keep compaction and Stateful Responses disabled. Baseline launch intentionally
starts exactly four services. If Google is part of the qualified configuration,
prepare its optional gateway only after baseline boot using the existing helper
and protected native session in this new phase, then apply the optional overlay,
proxy exclusion and pending native connection payload as described below.
Recheck effective bindings and the ordinary workflows affected by the refresh;
record snapshot, migration and readiness durations separately.

After an online rehearsal, remove only the rehearsal containers with their own
saved Compose/env composition. Restore QA with its original saved native Compose
composition, immutable image and three retained volumes, including its optional
Google overlay if used. Verify those actual bindings, private-route health and
an ordinary stored chat/file read. This restoration uses Compose directly;
`launch_stage.py` remains a first-boot guard for fresh preparations.

For the final consistent refresh, first drain work and stop all four approved
source writers. Repeat the same preparation with a fresh root/prefix and
`--source-stopped`, then launch, R2 and the same accepted runtime deltas. Restore
the exact source public CORS origins, public WebUI URL in environment and native
config, automation setting and any suppressed webhooks from the fresh source
baseline only at the route activation boundary. Preserve original source values
rather than unconditionally enabling background work. The route change remains
gated by readiness and a single active production writer.

Operational rollback still requires a separate timed native Compose/route
rehearsal using the retained old image, environment and original volumes, plus
health and an ordinary read through the restored route at the agreed write
boundary. `rehearse_rollback.py` proves disposable-copy downgrade and old ORM
reads only; it does not establish operational route restoration.

## Google and CC provider boundary: private staging

The direct Google OpenAI-compatible stream omits tool-call indexes. A later
Gemini-to-OpenAI CC model switch also rejected a 166-character signature-bearing
tool ID against the provider's 64-character limit; Anthropic rejected its
signature's characters in the same native history. Qualify the same optional
LiteLLM `v1.105.1` gateway for existing CC connections 1 (OpenAI), 2 (Anthropic)
and 4 (Google): its native non-Gemini request normalization removes the Gemini
signature from both call and result references. Keep every connection's complete
current model catalog. The existing Responses connection at index 0, core, native
tool loop, grants and artifact owners remain unchanged. The internal service and
file names retain `google-gateway-0122` to avoid a second gateway or route owner.

| Meaning or transformation | Existing owner and public contract | Consumer / classification |
| --- | --- | --- |
| Connection, keys and options | OpenWebUI admin `GET /openai/config` | Host helper projects only indices 1, 2 and 4; representation adapter. |
| Current CC model IDs | OpenWebUI `GET /api/models`, actual `urlIdx` entries for 1, 2 and 4 | Each existing connection's native `model_ids`; no gateway catalog list. |
| Provider protocol and signature | LiteLLM native `models/*` to `gemini/*`, `gpt-*` to `openai/gpt-*`, `claude-*` to `anthropic/claude-*` | Existing OpenWebUI CC tool loop; protocol adapter only. |
| Authentication and outbound proxy | Existing protected native session and candidate `webui.env` | Host helper writes mode-0600 gateway inputs; no new authentication flow. |
| Preparation and activation | `prepare_google_gateway.py` creates files and pending native payload | Operator applies native configuration and optional Compose overlay separately; call-order coordinator. |

The overlay uses the release image pinned by OCI digest, one worker, no database,
Redis, cache, fallback or gateway tool execution. The initial resource trial is
1 GiB RAM, 1536 MiB total memory/swap and 0.5 CPU; it is not a measured capacity
claim. No host ports or Traefik route are exposed. Preparation does not apply the
pending native payload, change WebUI proxy exclusions, start containers or invoke
a model. The operator owns those staging actions and the final rollback boundary.
Freezing `model_ids` preserves the captured catalogs; new CC models require a
later native catalog update. Stream/tool continuation, signatures, images and
resource use still require ordinary-route qualification before acceptance.

On the host, run `python3 prepare_google_gateway.py --root <prepared-phase-root>`.
First complete the native `gpt-6.1-sol` move to the existing Responses connection
at index 0. The helper verifies that ownership, the direct provider URL and CC
protocol of indices 1, 2 and 4, and each complete native catalog. It preserves
additional valid `gpt-*` and `claude-*` IDs without maintaining an exact second
catalog. It accepts fresh direct-provider input only; it cannot extend an already
running gateway or reset the original boot receipt.
It requires the already issued native admin sign-in response at
`admin-native-session.private.json` in that phase root; all protected inputs must belong to
the operator with directories mode 0700 and files mode 0600. It writes a public
`google-gateway/config.yaml` containing environment references, a protected
`private/google-gateway.env` with the existing `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY` and a fresh gateway master key, the full
original and pending OpenAI configuration
in `private/google-openai-{source,pending}.private.json`, and a private hash/count
receipt. Only the two `RELEASE_GOOGLE_*_FILE` selectors are appended to that
phase's protected `compose.env`; an existing gateway container or input is refused.
The optional overlay is `compose/openwebui.release-0122.google.compose.yml`.
Native API application, the WebUI `NO_PROXY` gateway alias and overlay composition
remain operator steps. LiteLLM 1.105.1 retains `--telemetry false` as a deprecated
no-op, rather than an active configuration control; no external callbacks are
configured. The original snapshot without `phase_root` is accepted only at the
task base with its recorded `boot_image_id` and all three original default volumes.

## Switch and rollback boundary

Prepare and test the exact image before the final write pause. Drain active
operations and stop the old WebUI and any other writers before the final
consistent DB/files refresh. Migrate only the candidate copy. Keep old data
unchanged. Enable the new production route only after readiness checks.

A simple switch to the untouched old DB is lossless only before new writes are
admitted. Rollback after new writes requires an independently verified compatible
downgrade or preservation/recovery of those writes; do not promise a lossless
return by pointing the old binary at an unverified migrated DB.

## Progress

- Current candidate image `sha256:a0f5752afafd24ae065190ef28d88717e9a29c739ccb23be1e2d3e7ff7bfe424`
  is built and booted on loopback. Its frontend, media behavior and native schema
  match the first qualified candidate; the additional Responses projection
  passes 21 checks in the installed image. The source production route is unchanged.
- Initial migrated snapshot passes source comparison, including all retained
  upload bytes, native defaults and the exact inherited foreign-key violations.
  Disposable-copy native downgrade and old-version ORM read pass; operational
  route rollback is still pending.
- Ordinary-user DOCX/XLSX/PPTX creation, preview, follow-up and native download
  are witnessed. Independent OOXML/openpyxl review finds no omitted source
  content. XLSX cached formula results total 22,503.80; each follow-up changes
  only the requested field/format plus native modification metadata. Six stored
  native File byte hashes match the UI downloads.
- Same-ID M4A/MP4 preparation and current-message transcription work. An audio
  follow-up does not retranscribe the historical attachment. Cross-user native
  File metadata and content requests return 404.
- The inherited OfficeCLI Filter allowlist omitted three current text models.
  Native valves now include the current IDs and remove three absent retired
  Claude IDs. Ten ordinary-user text models execute OfficeCLI; nine pass the
  exact help request first time. Gemini 3.1 Flash Lite initially sends the wrong
  parameter and succeeds after explicit correction. The eleventh target,
  `gpt-6-sol`, is not visible to that user; grants are unchanged.
- The observed Gemini-to-OpenAI/Anthropic failures are reproduced in one native
  presentation chat. With the outbound Responses projection and maintained CC
  gateway, that same ordinary-user history continues through Responses GPT,
  returns to Gemini with its original 166-character signed call ID, and continues
  through CC GPT and Claude. All four tool calls complete and report the correct
  slide title. Stored Google signatures and source history remain intact.
- Native Terminal transfer/publication returns identical document bytes.
  An ordinary native search returns five real results through the existing
  SearXNG. Earlier empty searches remain query/time dependent; source/runtime
  comparison gives no evidence of a version regression or a required search
  configuration change.
- During these checks all six relevant containers remain healthy, with zero
  restarts/OOM events. Current candidate WebUI memory peak is 1,717,960,704 bytes,
  gateway peak 693,460,992 bytes; host available memory is about 3.48 GiB.
- Native nested task reasoning parameters replace the inherited unsupported
  top-level value on the candidate; an actual title task succeeds. This accepted
  configuration delta must be replayed after a fresh source migration.
- Final current-data refresh, measured downtime, operational rollback rehearsal
  and production switch remain pending. These partial passes do not close the goal.
