# OpenWebUI 0.12.2 production and recovery

## Current status, 15 October 2026

The production switch is complete. R1-R10 passed bounded functional and
independent engineering acceptance; the goal is closed. The accepted source
head is `d1b73459904165c7c4854d7d9ada82c63f2dc78c`, delivered by
[PR #563](https://github.com/Kwentin3/corp-openweb-ui/pull/563) as merge commit
`a435076bacbe9a947f010d863516fd828f73016f`; their trees are identical.
[Exact-head Active CI](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/38730473557/job/116406713822)
passed. Runtime identity, data comparison and both maintenance windows are in
[Production acceptance](#production-acceptance-2026-10-15).

The sections describing candidate preparation and intermediate snapshots are
the reusable procedure and dated qualification history, not pending work.
For a plain-language delivery account see the
[15 October report](../commercial/COMPLETED_WORK_2026-10-15_OPENWEBUI_0122.md).

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

The accepted upstream base is `v0.12.2`, commit
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

The base Compose is `compose/openwebui.release-0122.compose.yml`.
During qualification its WebUI is bound only to host loopback port 18122 and
reached by an SSH tunnel. Production adds the route overlay; the acceptance
IP-allowlist overlay is not part of the final production composition.
Search reuses the existing native service; no parallel search deployment.

Read effective persisted configuration before boot. Disable candidate background
automations and temporarily disable the media Event until the copied storage and
pending markers are verified. Never rely on environment flags alone to override
persisted config. Do not share mutable source SQLite, upload paths or external
storage with the candidate. Copy secrets only into protected host-local files.

Production compaction was confirmed disabled. Preserve this setting. A pure
boundary probe on the opaque-carrier shape introduced by our Responses
preservation adaptation can detach that carrier from its retained tool batch.
This is a fix-acceptance constraint, not an independently reproduced unmodified
server failure; pristine reconstruction already drops those opaque items.
Active compaction is outside the accepted configuration.
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

For that route rehearsal, keep the online-refresh candidate's background work
disabled. It is an operator-only test copy, not the final consistent source.
Stop all four original source services, then enable the existing router with
both the route and acceptance overlays in **one** Compose operation. The temporary
`ipallowlist` must contain only verified deployment-host source addresses after
Docker NAT, without an `ipStrategy` that trusts forwarded headers. Verify real
hostname/TLS health, version and an ordinary owned chat/file read from that host.
An external request, including a spoofed `X-Forwarded-For`, must receive 403.
Check any available IPv6 route as well. Do not broaden the range to pass a probe.
Stop all five candidate services before starting the original four containers;
verify their unchanged identities/mounts and the restored public ordinary read.
Record the write pause and route-restoration duration. Then restore the retained
QA composition. Final cutover still requires a new `--source-stopped` snapshot;
omit the acceptance overlay from its production composition.

Retarget the existing recorder by modifying its sole active
`474-targets.conf` drop-in, retaining its original bytes in protected recovery
storage. During transition its native target list can contain the four original
and five candidate names; after acceptance retain only the five candidate names.
Reload systemd and restart only that recorder, preserving its state root,
history and cursors. Do not add an override, logger or recorder service.

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

## Qualification history before production activation

- Candidate image `sha256:a0f5752afafd24ae065190ef28d88717e9a29c739ccb23be1e2d3e7ff7bfe424`
  was built and booted on loopback. Its frontend, media behavior and native schema
  match the first qualified candidate; the additional Responses projection
  passes 21 checks in the installed image. The old production route stayed active
  during this qualification stage.
- Initial migrated snapshot passes source comparison, including all retained
  upload bytes, native defaults and the exact inherited foreign-key violations.
  Disposable-copy native downgrade and old-version ORM read passed. Operational
  route rollback was then completed in the separate rehearsal described below.
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
- Final consistent refresh and production activation are completed below.

The online full refresh copied 349 files in 80.472 seconds. Its second native
migration comparison preserves 31 users, 50 chats and 568 messages with zero
mismatches. The selected-answer Word Action also passes on that refreshed copy:
all three agreed paragraphs are retained and the stored file SHA256 matches.
The limited public route rehearsal passes real TLS/ordinary chat and file reads;
external requests receive 403, including spoofed forwarded headers. The original
four containers return without recreation, and an ordinary user downloads a
byte-verified file through the restored public route. Original start-to-public
readiness is 183.617 seconds; the full rehearsal write pause is 377.792 seconds.
The saved QA composition and volumes are restored. These results qualify the
route exercise, not final-source consistency or post-admission lossless rollback.

Keep the staging CPU and memory defaults while both WebUIs run. For production,
use the existing `RELEASE_{WEBUI,STT,TERMINAL}_{MEMORY,MEMORY_SWAP,CPUS}` selectors
to restore the original inspected upper bounds; zero CPU means no quota, matching
the original service. Restore the original Terminal process limit with
`RELEASE_TERMINAL_PIDS` as well. Set the optional gateway's native restart policy to
`unless-stopped` before its first final-phase start. Do not recreate that gateway
at the public activation boundary.

## Production acceptance, 2026-10-15

The public portal now serves v0.12.2 from image
`sha256:a0f5752afafd24ae065190ef28d88717e9a29c739ccb23be1e2d3e7ff7bfe424`.
Its active WebUI container is
`1799dfc897bc54c2312662b7197b65827db06e567b77e2ed277cbea014095c98`.
Exactly one running container owns the existing public router. The four original
services are stopped with their original IDs, images and three volumes retained.
The accepted QA and rehearsal volumes are retained as private evidence, with no
additional running WebUI. Existing unrelated services were preserved.

Final phase `/opt/openwebui-upgrade-0122/final-01` copies the source only after
all four original writers stop. Snapshot time is 64.501 seconds; launch through
health and strict R2 is 82.429 seconds; source-stop start through verified public
readiness is 463.846 seconds. The separate rollback rehearsal paused writes for
377.792 seconds. These are two separate maintenance windows.

The final comparison has zero mismatches: 32 users, 52 chats, 574 messages,
350 native File records, all 352 retained upload files, existing grants and
extension registries. Eight missing auth rows receive only the reviewed native
backfill, and 20 native configuration defaults are added. All 14 inherited
foreign-key violations remain unchanged. No new source loss or upload omission
is observed. This snapshot includes chats and documents created after rehearsal.

Embedded Chroma remains 1.5.9. Before boot, every vector file matches the stopped
source. After boot, all content tables, schema, migration records and index bytes
match the captured source: 25 collections, 2,448 embeddings, 102 files and
40,601,052 bytes. Only one native `acquire_write` startup row is added. The source
is not checkpointed or migrated. The manifest SHA256 is
`61c72890db4539f6029d2cc8352711ddec91f8e9f7a2bef6c151fd9e112af26f`.

Actual RAM/swap/CPU/process limits match the original four services. The private
gateway retains its ID across route activation and uses `unless-stopped`, as do
the other four services. The final environment and native config restore the
source public URL, exact CORS origins and automation setting. Media callbacks,
OfficeCLI and Terminal still target their new internal owners. Compaction and
Stateful Responses remain disabled.

An existing ordinary user session survives the switch and downloads the
unchanged original test file through public TLS. A public UI check on
`gpt-6.1-sol` executes OfficeCLI without manual tool selection and produces the
exact requested three-paragraph answer. Its native selected-answer Word Action
returns a real, owned DOCX; independent XML inspection finds all three paragraphs
unchanged, and the browser's downloaded byte hash matches
`38ed514e1e0b529f5999fa1a8ce2118eec40228ee192f89e50ce6f5c78882a6a`.
The public Gemini route also completes M4A preparation and full current-message
transcription, preserving the spoken project's name, meeting time and assignees.

The existing recorder is retargeted through its same `474-targets.conf` drop-in
to the five new services, preserving its history and cursors. No duplicate logger
is deployed. Initial public checks report zero restarts/OOM events and about
5.18 GiB available host memory. This is bounded functional/resource evidence,
not a sustained concurrent-load capacity claim.

Protected receipts are in the final phase: `migration.private.json`,
`vector-copy.{before-boot,after-boot}.private.json`, `fresh-phase.safe.json`,
`ready-private.safe.json`, `public-activated.safe.json`,
`selected-answer-export.safe.json` and `runtime-postcheck.safe.json`.
The reviewed source delivery is PR #563; runtime identity is the image above,
not a mutable tag. After public admission, preserve candidate writes before
recovery: the tested untouched-old-DB return is not a lossless rollback for new
customer writes or newly used 0.12 features.

## Remaining adaptations and upstream follow-up

There are two source overlay packages, changing seven OpenWebUI source files:

| Package | Scope | Removal condition |
| --- | --- | --- |
| [Responses context](../../deploy/openwebui-patches/tool-context-v0.12.2/README.md) | Three backend files: reconstruct same-model opaque reasoning and tool-result images, admit API fields, and project long outbound Responses call/result IDs without changing stored history. | A selected upstream version passes the same reconstruction and ordinary-chat continuation checks without the overlay. |
| [Media upload](../../deploy/openwebui-patches/media-upload-v0.12.2/README.md) | Two backend and two frontend files: bounded local upload writes, claimed processing handoff, and authoritative prepared-attachment metadata refresh. | A native extension path passes the same same-ID preparation, waiting, failure, Send/STT and ordinary-document checks. |

The old history-ordering backport is already replaced by native OpenWebUI.
Office model allowlists, task parameters and extension activation use existing
native configuration. The one private LiteLLM service is an additional maintained
protocol adapter for existing CC connections; it owns neither chat history nor
tool execution. These remaining costs are explicit, not a patch-free core claim.

Published on 15 October:

- [Issue #32473: stateless Responses reasoning reconstruction](https://github.com/open-webui/open-webui/issues/32473), including image provenance and the qualified compaction acceptance constraint.
- [Discussion #32474: cross-provider call ID compatibility](https://github.com/open-webui/open-webui/discussions/32474).
- [Concrete prepare-before-Send media workflow](https://github.com/open-webui/open-webui/discussions/24239#discussioncomment-18949752) in the existing upload-hook discussion.

The source reproductions were rerun against unmodified release commit
`6a18585ff4c2e5f6805f682222cfbc46dc669ef8` and `dev` commit
`613eac51c5c9cc67065998282af16e8016d5a2cb`. They execute actual extracted functions
without a database or provider, not a full unmodified `dev` portal acceptance.
Only synthetic fixtures were published. The reports do not establish upstream
agreement, a merged fix or a delivery date.

## Local evidence and repository closeout, 15 October

The completed upgrade and Office guidance worktrees were removed after proving
their commits are in the accepted `main` and moving their useful ignored files
to `local/repository-preservation-20261015/`. The retained manifest
`task-evidence.private.json` and `verified.safe.json` cover 21,191 files and
797,596,795 bytes with matching SHA256 values before and after the move.
Generated dependency/test/build caches are outside that content manifest and
remain retained locally because automatic policy rejected their recursive
deletion. This is not a claim that every cache was removed.

Seven fully merged local branches and the two completed remote task branches
were retired; their original refs are in `removed-branch-refs.safe.json`.
Independent older worktrees, the Broker Reports WIP archive/bundle and all
production/recovery volumes are preserved. Host cleanup or retirement of the
stopped 0.11.4 recovery stack is not part of this repository cleanup.
