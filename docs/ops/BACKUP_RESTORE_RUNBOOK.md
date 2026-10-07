# Backup Restore Runbook

## Backup

Запуск:

```bash
bash scripts/backup.sh
```

Скрипт сохраняет:

- Docker volume `openwebui_data`;
- Docker volume `stage2_stt_data` после реализации quiesced backup в скрипте;
- server-local `.env`, если файл существует;
- опционально volume `traefik_letsencrypt`, если он создан.

Backup directory по умолчанию:

```text
/opt/backups/openwebui-prd0
```

Provider keys могут находиться в `.env` и/или в OpenWebUI persistent data, если secondary provider добавлен через Admin UI. Поэтому backup считается секретным.

## Retention

`scripts/backup.sh` читает retention из environment или server-local `.env`:

```env
BACKUP_RETENTION_DAYS=7
```

Для PRD-0 используются простые значения:

- `1` - test retention на 1 день;
- `7` - default для короткого пилота;
- `30` - около месяца.

Текущий `scripts/backup.sh` ещё не включает `stage2_stt_data` и архивирует
работающий `openwebui_data`; поэтому он не считается application-consistent
для Broker/STT SQLite. До исправления использовать один из двух режимов:

- cold: остановить writers, архивировать volumes, запустить writers;
- coordinated: поставить canonical mutations на паузу, выполнить SQLite Online
  Backup, скопировать только immutable payloads из manifest и проверить hashes.

Неконтролируемый `cp` или tar работающей SQLite с отдельно меняющимся payload
root запрещён.

## Restore

### Issue #474: clean staging, then restore and migration

The [2026-10-02 upgrade scope](https://github.com/Kwentin3/corp-openweb-ui/issues/474)
permits preparation and isolated restoration. The owner's subsequent direction
separates clean-platform development from full data copying: start an empty
official OpenWebUI and bring in integration source/configuration incrementally.
The owner-approved 2 October core-data restore/migration rehearsal passed on
6 October; its exact scope and limits are recorded below. A fresh coherent
cutover backup and migration of the current production data remain required.
The owner's 7 October decision replaces the earlier data membership: preserve
accounts, password hashes, roles/groups and effective rights, plus Skills,
Prompts, Harness, Tools/Functions and necessary model/configuration settings.
Do not transfer historical test chats, notes, result folders, any old
attachments/transcripts, document corpora, vectors or Terminal working files.
The previous 45-file ambiguity and mixed-chat exception are superseded.
New chats/files and transcription still require ordinary product acceptance.
Keep the broker code work in source control, with #516/NDFL frozen and its
runtime processing inactive. This supersedes any earlier requirement to copy
the financial corpus into the new installation; it does not authorize deleting
the originals or existing backups.
Production downtime requires approval of a concrete window. The general restore
commands below describe production maintenance, not creation of the clean stand.

Use `compose/openwebui.staging.compose.yml` alone, with a separate private env
file containing `STAGING_WEBUI_SECRET_KEY`, `STAGING_ADMIN_EMAIL` and
`STAGING_ADMIN_PASSWORD`. These must be new staging credentials, not production
keys. It declares a pinned official amd64 image, its own data volume and internal
network, explicit resource limits and no published host port. Initially providers,
search, updates and model downloads are disabled; no legacy loaders, core patches
or production data are mounted. Access through a private SSH tunnel bound to
operator localhost port 18084, forwarding to the current inspected staging
container IP on port 8080; resolve it again after recreation. Add each
needed service/extension only after its own paths, grants and callback addresses
have been checked. Synthetic test data belongs only to this stand.

```bash
docker compose --env-file /private/staging.env -f compose/openwebui.staging.compose.yml config --quiet
docker compose --env-file /private/staging.env -f compose/openwebui.staging.compose.yml up -d
```

Add OfficeCLI and Terminal with their staging declarations, not the production
files referencing `openwebui_web`. Set a new `STAGING_TERMINAL_API_KEY` and a
qualified `STAGING_OFFICECLI_IMAGE` in the same private env file. OfficeCLI uses
the existing [Dockerfile](../../services/officecli-openapi-proof/Dockerfile):

```bash
docker build -f services/officecli-openapi-proof/Dockerfile -t corp-openwebui/officecli-staging:issue474 .
docker compose --env-file /private/staging.env -f compose/openwebui.staging.compose.yml -f compose/openwebui.staging-terminal.compose.yml -f compose/openwebui.staging-office.compose.yml up -d
```

An existing immutable OfficeCLI image can be reused after exact installed
package/source parity, CLI version and writable-layer checks; this reuses the
service artifact without copying production state. Record its image ID privately
and retain the source build recipe. The initial 2026-10-02 component check used
OfficeCLI 1.0.152 with 7/7 Python sources equal to the selected repository revision
and no writable-layer changes. Terminal uses the same pinned official artifact
as the accepted production service, with a new `terminal_home` volume. Both
services have no published ports and belong only to the staging internal network.
OfficeCLI's callback is `http://openwebui:8080` inside that network.

Configure native Tool Servers with ID `officecli`, Session authorization, and URL
`http://officecli-openapi-proof:8080`, schema path `openapi.json`. On 0.11.4, set
these native custom headers on this connection:

```json
{
  "X-OpenWebUI-Chat-Id": "{{CHAT_ID}}",
  "X-OpenWebUI-Message-Id": "{{MESSAGE_ID}}"
}
```

Session auth forwards the token; it does not by itself forward the native chat
and message IDs required for result publication. The installed native header
builder resolves these placeholders from request metadata. Without them, a real
ordinary-chat creation attempt returned HTTP 400 before publishing a file. Keep
the existing fail-closed ownership check; do not ask the model to invent IDs or
put them in document content. This per-connection setting requires no core patch
or container recreation. For a streamed model that supports usage reporting,
enable its native `meta.capabilities.usage` so the server requests and persists
provider token counts; retain the full cost reserve if a failed run lacks usage.

Configure native Terminal ID `office-linux`, URL `http://open-terminal-office:8000`, bearer auth
using only the new staging key. Preserve the previously accepted trusted-team
boundary and explicit native access grants. Register source from the selected
revision using the existing Office workflow components; keep Filter/Skill inactive
until dependencies and the intended model route are qualified. Service health,
schema discovery and administrative Terminal proxy success are component evidence,
not ordinary-chat acceptance.

The 2026-10-02 stand also exercised native Files access with two synthetic
ordinary users: the owner downloaded matching bytes, the other user received
404, and their Terminal homes differed. The installed transfer Tool staged a
matching copy, retained the source and rejected the foreign file. This validates
the HTTP/component boundary, not model selection or the full ordinary-chat
scenario. A later deterministic component check also ran a real native Terminal
command on a staged copy, published its verified output through the installed
Tool and native event emitter, and read the persisted chat attachment back.
The browser displayed the attachment and its native link opened the exact text
result inline. Native Files download bytes matched the Terminal output; the source
remained unchanged and another user's download was denied. This additional
chain still does not prove a model-selected tool call.

Deterministic requests under an ordinary-user token also exercised the real
OfficeCLI service: create and edit DOCX/XLSX/PPTX, download both versions, verify
ZIP integrity and the expected original/added content, retain source bytes,
read persisted result attachments from the chat again and deny another user's
download. These checks cover adapter/CLI/Files/event compatibility; they do not
qualify model-generated commands or multiple-source scenarios.
The ordinary fixture owner then opened each saved chat in the browser and
downloaded DOCX/XLSX/PPTX through the native attachment controls; each download
hash matched its verified result. Native DOCX preview displayed both expected
paragraphs. These are existing-result/browser checks, not model invocation.

On 2026-10-03, after the connection-header correction above, an ordinary-user
browser chat selected the existing direct model and created a new XLSX through
OfficeCLI. Independent ZIP/XML inspection matched all six requested cells,
including numeric types, with one sheet and no extra data. The native result
attachment survived reload; the owner downloaded matching bytes and another
user could not read the file or chat. MCP performed the model invocation and
reload check; after its browser closed during download, a local Playwright
fallback qualified only the same persisted attachment's download, with model
dispatch blocked. Native aggregate input/output usage was retained privately.
This accepts that small XLSX scenario only. The earlier failed DOCX run retains
its worst-case cost reservation and is not accepted. This describes the initial
checkpoint; subsequent ordinary-chat acceptance is recorded below.

A further synthetic PPTX fixture exercised the nearest attached template,
native slide cloning and a follow-up from the last published result after
reloading the chat record. The two original slides, layouts, masters, theme
and media were preserved: 18 original parts were byte-identical and one slide's
XML differed only in namespace serialization, with identical canonical XML.
The third slide retained editable shapes and its picture. Fresh source/result
renders showed the expected preserved slides and changed clone title without
visible clipping. A native browser download after page reload matched the
verified result hash. Commands were deterministic; model selection and a
model-driven continuation remain unqualified.

Two attached synthetic XLSX sources were inspected by their explicit native
IDs. An omitted ID failed with HTTP 422 rather than silently selecting one
workbook. Independent ZIP/XML reads matched all inspected source cells; the
published result retained both rows and their total. Source and intermediate
bytes remained unchanged. Native column-width adjustment removed a clipped
header in the first render; the fresh final render and browser download after
reload were verified. Another user's final download returned HTTP 404. This
qualifies deterministic multi-source transport, not model-generated analysis.

A syntactically valid ZIP/PPTX with a missing slide relationship was rejected
before editing with HTTP 422 and `PPTX_SOURCE_VALIDATION_FAILED`. Native findings
identified the unresolved image relationship. No new File or assistant result
was published, source bytes remained unchanged and temporary directories were
removed. The ordinary model's explanation of this error remains unqualified.

Import only the two accepted shared templates, `stt-summary` and
`stt-meeting-protocol`, through native Prompts create/import. Preserve command,
name, content, parameters and public read grants; assign a valid staging owner
instead of copying production user identities into the empty stand. Retain
source identity privately for the later full migration. The 2026-10-02 check
confirmed unchanged content and ordinary-user read access. In the browser both
slash commands opened the native `TRANSCRIPT_WITH_SPEAKERS` variable dialog and
inserted a synthetic transcript into the composer without an unresolved variable.
No message was sent. This proves template selection and expansion, not model
output. No STT prompt-catalog processor or runtime SQLite reader is installed.

Add search with `compose/openwebui.staging-search.compose.yml` only when public
search/page-fetch checks are ready. Set a new `STAGING_SEARXNG_SECRET`, point
`STAGING_SEARXNG_CONFIG_DIR` to a staging copy of the tracked `deploy/searxng/`
configuration, and set `STAGING_OUTBOUND_PROXY` to the existing approved outbound
proxy. Do not copy production search secrets or mount production volumes. The
overlay retains qualified search image digests and gives SearXNG/Valkey separate
named volumes. Only OpenWebUI and SearXNG join the additional staging egress
network; OfficeCLI, Terminal and Valkey stay on the internal network. No ports
are published. Keep model providers disabled for these component checks.

```bash
docker compose --env-file /private/staging.env -f compose/openwebui.staging.compose.yml -f compose/openwebui.staging-terminal.compose.yml -f compose/openwebui.staging-office.compose.yml -f compose/openwebui.staging-search.compose.yml config --quiet
docker compose --env-file /private/staging.env -f compose/openwebui.staging.compose.yml -f compose/openwebui.staging-terminal.compose.yml -f compose/openwebui.staging-office.compose.yml -f compose/openwebui.staging-search.compose.yml up -d
```

Check effective native Web Search settings after recreation: persistent database
configuration takes precedence over bootstrap env. Use the native admin settings
API/UI, not SQL edits. The intended page-loader path uses `searxng`, the internal
`http://searxng:8080/search?engines=duckduckgo%20web` URL, search-loader proxy
trust disabled, web-loader bypass disabled
and search embedding/retrieval bypass enabled. This reads actual pages without
introducing an embedding provider. A real search result alone does not prove
page retrieval or an ordinary-chat answer with sources. Re-resolve the staging
container IP for the private SSH tunnel after recreation.

The existing host proxy may be reachable only from the production bridge under
UFW. Inspect its actual listener and firewall first. For a separate staging
egress bridge, allow only that bridge/subnet to the existing proxy address and
TCP port; preserve the original production rule and deny policy. Do not expose
the proxy publicly or restart it to accommodate staging. Resolve bridge/subnet
from the current staging Docker network, not a historical hardcoded address.
For example, with verified private operator variables:

```bash
ufw allow in on "$staging_bridge" from "$staging_subnet" to "$proxy_address" port "$proxy_port" proto tcp comment 'Issue474 staging page-loader proxy'
# Remove this task-owned rule before removing/recreating its staging network:
ufw delete allow in on "$staging_bridge" from "$staging_subnet" to "$proxy_address" port "$proxy_port" proto tcp comment 'Issue474 staging page-loader proxy'
```

Store the resolved rule and its inverse in protected operator evidence. A
successful direct proxy probe proves reachability only; repeat the actual native
page-loader request under the ordinary fixture user's authorization.

SearXNG's engine requests have their own native proxy configuration; OpenWebUI's
proxy env does not configure that separate container. If direct engine requests
are rejected, test the existing approved proxy through
[`outgoing.proxies`](https://docs.searxng.org/admin/settings/settings_outgoing.html)
in the staging settings file: `all://` maps to a list containing the actual
`STAGING_OUTBOUND_PROXY` value. SearXNG does not expand that Compose env variable
inside a bound YAML file. Keep the original tracked settings privately as the
inverse, record the rendered configuration hash, and recreate only staging
SearXNG to apply/revert it. Retain engines, TLS verification and limiter settings.

On 2026-10-02 the ordinary fixture user fetched the public Python pathlib page
through the native OpenWebUI loader: 59,671 characters, expected source content,
TLS verification enabled, no embedding/model calls. General search still returned
no results: Brave rate limiting and DuckDuckGo/Startpage CAPTCHA were reproduced
on both the new and existing SearXNG. The native outgoing-proxy alternative
returned the same refusals and was reverted on staging. Do not mark search/answer
with sources accepted from the successful independent page-fetch check.

On 2026-10-03 the installed `duckduckgo web` JSON driver returned relevant
English and Russian public-query results, including official Python pages.
It is already declared in the pinned SearXNG defaults; the native query URL
selects it explicitly without replacing SearXNG, adding a provider/key or
changing its configuration. The installed OpenWebUI SearXNG client preserves
the URL's engine parameter while adding the user's query. Keep this distinction
from the CAPTCHA-failing `duckduckgo` HTML driver. Bing was rejected: irrelevant
links were already present in its external HTML response; the existing proxy
returned no usable links. Do not substitute nonzero result counts for relevance.

Persist the selected URL through the native retrieval settings API/UI as well
as Compose, then recreate only the owned WebUI with all currently installed
staging overrides. Compare effective settings after recreation. Roll back by
restoring `http://searxng:8080/search` and `WEB_SEARCH_TRUST_ENV=true` in both
native settings and the staging Compose declaration; this restores the previous
configuration, including its known search failures. No core patch or search-image
rebuild is required. After
selection, verify loaded page content and original source URLs via the ordinary
fixture user's native search endpoint; model-generated answers/citations still
require their separate browser acceptance and authorized budget.

For this pinned image, the async `safe_web` connector rejects the private
environment proxy, producing empty documents. The native
`WEB_SEARCH_TRUST_ENV=false` setting uses the already declared staging egress
network for public page requests; model connections retain the existing proxy
environment and `NO_PROXY`. Do not enable local web fetch, weaken TLS or patch
the address guard to accommodate the proxy. Check actual nonempty content,
not `loaded_count`: upstream can count an empty failed document as loaded.
Record any empty source URLs and qualify model citations only against pages
whose content was actually retrieved.

After reconciling those two native settings and recreating the same WebUI
image on 2026-10-03, both ordinary-user search requests returned three nonempty
pages. English page lengths were 4,293 / 35,491 / 871 characters; Russian page
lengths were 15,119 / 22,198 / 132,129. The actual official Python source URLs
returned by search were fetched independently through the native single-page
endpoint, and their complete extracted content matched. Ranking selected a
Python 3.10 page for the unversioned pathlib query; no fixed preferred URL was
injected into the results. Both selected settings survived recreation, the
other five staging container IDs and all seven production identities stayed
unchanged, and no model/embedding provider was called. This qualifies native
search and page retrieval, not the ordinary-browser model answer/citations.

The existing host flight recorder is reused for staging with its own protected
state directory and the six staging container names as `--targets`. The
production recorder and its history are retained. The initial staging observer
runs as a bounded transient systemd unit (128 MiB, 5% CPU) and has produced
nonempty state; this temporary observation is not the final production service
installation. Record the installed recorder source identity and update the
existing production selector only with the approved release.

### Issue #474: media component and approved staging bridge

The fifth staging override is `compose/openwebui.staging-stt.compose.yml`. Set a
new `STAGING_STT_INTERNAL_API_KEY` and a qualified immutable `STAGING_STT_IMAGE`.
Use the existing STT Dockerfile for a fresh source build. A qualified local base
can also be reused for an explicit domain-source-only rebuild; record the base
image identity and changed package hash. Never update source inside a running
container. The component stand has its own `stt_data` volume, internal network
only, no production data mount, no provider key and no stub transcripts. Native
Prompts replace the disabled prompt-catalog/post-processing integrations.

In the 2026-10-02 component check real FFmpeg prepared MP3 from short synthetic
MP3, M4A and MP4 inputs. Returned bytes matched the SHA header; independent
FFprobe confirmed one MP3 audio stream and no video. A valid silent video showed
that FFprobe returns success with an empty audio-stream array. The STT source now
rejects that case as `source_has_no_audio_stream`, rather than trying FFmpeg and
misclassifying it as a retryable conversion failure. The focused regression
failed before the fix and all three preparation tests pass after it. The rebuilt
STT artifact matches all 19 selected Python sources; actual silent-video HTTP422,
bad internal auth HTTP401, missing provider auth HTTP503 and temporary-directory
cleanup were checked. No STT/model provider call occurred.

Before the separately approved bridge trial, uploading a synthetic MP3 on the
unmodified official image through the ordinary-user native Files API without
Send reproduced `pending → failed` during upload-time processing. Native
dictation configuration uses the accepted `web` engine. This established a
timing gap, not successful transcription or dictation.

The version-specific staging exception touches four upstream source files:
native local storage for bounded write/hash, Files upload for an opt-in handoff
to the registered Event Function, the native file client for final metadata
refresh/error handling, and MessageInput for the resulting filename/size. The
native Function/cache owner discovers optional upload hooks only on active
Event Functions. Classification and lifecycle remain in the registered extension;
the core bridge does not contain media rules or a separate registry. With the
extension disabled or removed, native file processing remains unchanged. Install
the STT dependency before enabling the intake. Disable the intake and STT Filter
together when removing the integration.
No new gateway, user registry, Files store or copied core service module is used.

`accept_upload` is our added hook, not a documented contract of the unchanged
upstream. The four-file exception performs no media conversion or Lemonfox
call. Event Function `stage2_media_intake` runs inside OpenWebUI and depends on
its internal File models and Storage API; it owns replacement, cleanup and
recovery while FFmpeg runs in the existing STT sidecar. The separate post-Send
STT Filter obtains or reuses a transcript and supplies text to the selected
ordinary model. Keeping an MP3 as a native user attachment does not authorize
forwarding its bytes, media URL or base64 to that model. This remains an explicit
core exception requiring a qualified custom image on updates. At the next
upgrade, look for a native replacement first and repeat the affected product
checks before deciding to retain the exception.

Source inspection shows that v0.11.4 already queues messages while attachments
upload and resumes through its native `onUpdate`/`processNextInQueue` path.
Retain that implementation; do not port the retired compiled-chunk wait patch.
The subsequent checks below qualify specific queue, cleanup and model cases;
they do not imply complete media acceptance. Build frontend changes from exact upstream source;
never edit compiled chunks. Keep the upstream source hashes and exact diff in
protected operator evidence; static AST and diff applicability checks do not
replace image/build/product verification.

**Apply each new core diff only after the separate approval required by #474.**
Qualification must cover ordinary documents, unchanged source bytes/rights,
MP3/M4A/MP4 replacement under the same File ID, cleanup before completion,
the accepted three-attempt/420-second retry and restart reconciliation, cached
transcripts and ordinary native Send. Until a paid budget is approved, keep the
provider key empty and prove the refusal path. Rollback selects the untouched
official image and disables the new
intake/Filter; retain staging files for investigation. Remove the exception when
upstream supplies equal bounded upload, pre-processing delegation and completed
metadata semantics and those pass the same product checks.

The owner approved the exact four-file trial on 2026-10-02, then separately
approved a one-line correction preserving the native SSE error during metadata
refresh. The full corrected diff SHA-256 is
`e7d4be27abbfe57ef970f1074a3f861b9ebac74d44eaee39a9515bf765a236df`,
against upstream commit `8bd8b4fac5e059578ac0c74b3c18d11139f88b7d`.
Both approvals cover staging trials; they do not authorize production, merge/CD
or paid calls. The original trial exposed the missing warning for a deliberately
invalid synthetic DOCX. After the approved correction the ordinary browser
showed the native warning; a valid synthetic DOCX completed processing with
unchanged bytes. The browser then prepared M4A as MP3 with final metadata and
retained that attachment after reload. Native MP3/M4A/MP4 and generic-MIME checks
also passed on the corrected image. With the Event Function temporarily disabled,
an ordinary native text document still completed; the same extension was then
reenabled. These checks did not invoke a model or transcription provider.

The native frontend build ran on the operator workstation with Node 22.19.0,
unchanged package.json/package-lock and the standard npm build. The first
4096 MiB heap attempt exhausted memory; the successful build used 6144 MiB.
The runtime recipe replaces the base static directory with the complete rebuilt
bundle and copies the two exact backend files onto the pinned official image,
without runtime package installation. Image qualification checks all 5604 static
files and both backend hashes, including the absence of leftover base chunks.
Preserve the untouched official image and the previous trial image for rollback.

The exact approved install inputs are tracked in
[`deploy/openwebui-patches/media-upload-v0.11.4`](../../deploy/openwebui-patches/media-upload-v0.11.4/).
`apply_proposal.py` requires the pinned Git HEAD and all four source hashes,
rejects partial/foreign states and makes an exact repeat a no-op.
An isolated pinned-source worktree verified check-only, exact application,
idempotent repeat, and rejection before writing for mixed sources, foreign
source bytes, an altered diff and another Git HEAD. The probe worktree was
removed and the qualified build checkout remained unchanged.

Set operator paths to a disposable upstream checkout, this repository and a new build context;
never run the frontend build in a production container. Use Node 22.19.0 and a
machine with sufficient free memory for the qualified 6144 MiB heap:

```bash
git -c core.autocrlf=false clone --depth 1 --branch v0.11.4 https://github.com/open-webui/open-webui.git "$upstream_checkout"
python "$repository/deploy/openwebui-patches/media-upload-v0.11.4/apply_proposal.py" "$upstream_checkout" --check
python "$repository/deploy/openwebui-patches/media-upload-v0.11.4/apply_proposal.py" "$upstream_checkout"
# Retain the verified checkout's package.json/package-lock:
cd "$upstream_checkout"
CYPRESS_INSTALL_BINARY=0 npm ci --force --no-audit --no-fund
NODE_OPTIONS=--max-old-space-size=6144 APP_BUILD_HASH=8bd8b4fac5e059578ac0c74b3c18d11139f88b7d-474-e7d4be27 npm run build
```

After success, prepare a new context containing the complete `build/`, exact
patched `backend/open_webui/storage/provider.py` as `code/storage/provider.py`,
and exact patched `backend/open_webui/routers/files.py` as `code/routers/files.py`.
Use the tracked `runtime.Dockerfile`. Record source/lock/diff hashes, Node version,
the build exit code, every static-file hash and the context hash before image
build. The qualified runtime build uses `--network none --pull=false --memory
512m --cpu-shares 512`; its official base must already be available. Verify the
image labels, both backend hashes and the entire static-file set before selecting
the image. Do not infer build provenance from a tag or successful healthcheck.

The optional sixth overlay is
[`openwebui.staging-media.compose.yml`](../../compose/openwebui.staging-media.compose.yml).
Set `STAGING_MEDIA_TRIAL_IMAGE` to the exact qualified image ID and include this
overlay after the base/Terminal/Office/search/STT files. Resolve Compose config
first, then recreate only staging OpenWebUI with `up -d --no-deps --pull never
openwebui`. Preserve its own volume and register the tracked media Event Function
through native Functions; enable it only with the STT dependency present. Keep
the STT Filter inactive until its intended post-Send route is qualified. Rollback
uses the same image selector and the previous qualified image ID; a full exception
rollback additionally disables both extensions and selects the official image.

Native ordinary-user upload/SSE/download checks prepared real MP3 from MP3,
M4A and MP4, including a generic MIME upload. Final name, MIME, size and hash
matched the downloaded audio under the same File ID. Converted sources were
removed before completion; another user's download was denied. In the browser,
a fresh M4A upload became an MP3 attachment and retained the same identity and
metadata after reload. No Send or transcription occurred in these checks.

A synthetic valid MP4 padded to the accepted 809,586,557-byte upload volume
passed the native server upload/conversion path. Sampled cgroup anonymous memory
increased by about 4.4 MiB; total cgroup peak reached the 1.5 GiB limit through
file cache, without OOM or restart. The padding proves byte-volume handling, not
a long recording or public proxy upload. A subsequent ordinary-browser check of
the same 809,586,557-byte volume on 2026-10-04 prepared a 9,363-byte MP3 under the
same File ID and removed the source video. Pressing Send during preparation
queued one draft and emitted one completion only after preparation completed.
The deliberately disabled model connection then returned model-not-found; no
model or STT provider call was made. The prepared attachment survived WebUI
recreation. This accepts browser byte-volume and the early-Send queue, not
long-speech transcription or a successful full large-media chain. Memory
sampling covered part of the upload and is not a whole-upload peak measurement.

A controlled SIGKILL of the owned staging WebUI after durable audio write but
before native File path commit exposed an uncommitted-output collision. Event
Function 0.1.1 reconciles only that File ID's canonical unclaimed output while
the native row still points to its source. The original interrupted File then
completed automatically on attempt three at its unchanged due time, no earlier
than the required 420-second delay. Audio bytes/hash, source removal, cleared
pending output and foreign-access denial were checked. This qualifies that real
recovery window; it does not qualify every failure/cleanup or ordinary Send.

A valid video with no audio also passed the negative native browser lifecycle:
two immediate preparation attempts, then attempt three no earlier than the
420-second due time. The browser displayed the final error and removed the
failed attachment from its queue. The source bytes were deleted, native and
extension source paths cleared, and preparation temporary directories absent.
The failed File row remains; its unchanged native content route returns HTTP
400 when its path is empty. No transcription or model request was made.

The installed inactive STT Filter was also invoked as a component with an
ordinary fixture user's native audio File. Its real sidecar request returned
HTTP 503 because the provider key was absent. The returned context recorded
failure, outbound audio collections were cleared, and native audio bytes and
metadata stayed unchanged with no transcribed marker or temporary files. The
Filter remained inactive; no provider, model, event or browser Send acceptance
is implied by this guard check.

The 2026-10-04 ordinary-browser M4A qualification used one real Lemonfox STT
request (14.90725 seconds). Its exact synthetic source text, speaker label,
timestamps, owned artifact and foreign-access denial matched. The first model
response failed on native outbound proxy CONNECT HTTP 503; the transcript and
prepared attachment remained available. After unpaid transport checks succeeded,
separately reserved manual model generations reused the cached transcript,
including after STT recreation with the provider key disabled. They made no
further STT jobs and preserved the original failed response.

That real response exposed a version boundary: full transcript in legacy
`content`, summary only in structured `output`, and summary only in the browser
before and after reload. Native audio-context Filter 0.2.4 projects its existing
wrappers into the existing assistant output text parts and preserves provider
text, annotations, IDs and tool/reasoning output. This is a representation
adapter, not another transcript owner or core patch. Replaying the actual response
through the installed native output reader matched persisted content, and a new
ordinary-browser generation passed full transcript live/reload, native audio
preview, byte-identical download and foreign chat/file denial. This accepts the
short M4A recovery/cache scenario; the original M4A failure remains recorded.

A subsequent short spoken MP4 passed ordinary browser upload/preparation and
its first Send, one real STT request (15.789625 seconds) and the selected model's
response. Full transcript, speaker/timestamps, reload, native player/download
byte equality and foreign-access denial passed. Both transcripts survived STT
recreation with the provider key disabled. The MP4 transcript differs from the
written speech source only by Russian yo/e orthography; actual provider text
was preserved without correction and all source facts matched. This accepts
the short prepared MP4 scenario. The separate byte-volume/early-Send check above
does not qualify long speech through that full chain. The 2026-10-04 native
dictation trial with Chrome and a WAV-backed test microphone returned
`audio-capture` and no text; a separate MediaRecorder check received audio.
Its cause remains unresolved. This synthetic device trial proves neither
successful dictation nor failure on a physical microphone.

A 2026-10-05 diagnostic repeat with the same native voice button, source WAV
and Chrome version returned `no-speech`. Browser audio logs distinguish two
`FAKE` streams for the media-capture path from a separate default-device
`PCM_LOW_LATENCY` input opened for recognition. Therefore the WAV-backed
getUserMedia check does not establish what SpeechRecognition actually heard,
and the earlier claim that test flags exclude physical input is unproven.
The primary cause of the original `audio-capture` remains unknown; the error
was not reproduced consistently. No recognition-result injection or core
change was used. The composer/history remained empty, the browser closed,
auth removed and paid accounting unchanged. Stop this automatic fake-device
replay: accept dictation only after an ordinary browser/manual microphone check
with a safe phrase and no Send. Do not fix the native component merely
to make this inadequate harness pass. Private diagnostic receipts and the
browser audio log retain this distinction; no raw microphone recording is
saved by the diagnostic operator.

That manual check was accepted on 2026-10-05. The owner operated the native voice
button in ordinary visible Chrome 154, authenticated as the synthetic staging
user, with the native `web` engine and automatic Send disabled. No fake device,
recognition replacement or result injection was used. The composer contained
27 characters after recording ended, and the owner confirmed that the microphone
worked. This accepts native dictation to the composer, without claiming Send,
a chat-model response, uploaded-media STT or an exact match to the operator's
suggested phrase. No raw microphone audio or dictated content is published.
Protected evidence is `owner-acceptance-20261005.json` and the private visible
browser/observation receipts. The earlier synthetic failures remain diagnostic
limitations rather than evidence of a current product failure.

The 2026-10-05 outgoing-request check used the existing MP4 transcript in a
native browser fork of the ordinary user's accepted chat. Native Regenerate
passed the same MP3 File ID to the installed Filter. Its cached route required
no new STT job. The installed OpenAI client actually sent HTTP
`POST /v1/chat/completions`, `Content-Type: application/json`, to a temporary
credential-free receiver at `http://127.0.0.1:18085` inside the staging container.
This was a diagnostic destination configured through the native connection API,
not a new provider, replacement Filter, replay of a pure serializer or browser
request substituted for server egress. Auxiliary tasks and built-in tools were
disabled for this bounded check. The receiver returned HTTP503 deliberately,
without forwarding the request or generating a model result.

The emitted JSON selected `gpt-5.4-mini` and contained only `model`, `messages`,
`stream`, `stream_options`, `max_completion_tokens`, `reasoning_effort` and
`service_tier`. `messages` held one user message with string content including
the entire cached transcript. No files/media fields, media URL or data/base64
encoding were found; there was no authorization header or tool payload. The
structural receipt excludes transcript content and secrets. This proves the
actual native outgoing body for the cached MP4 route; it is not a historical
capture of the earlier paid request to `api.openai.com`, nor a new successful
model-response acceptance. The accepted real M4A/MP4 checks above establish the
preceding STT and browser-result segments separately.

The exact checked runtime was image
`sha256:c4ba3bda7e228f99a246f1d823dfe2a8830dbd8fad6966d2e1862350fb8be423`,
container `6aa32396208bbb6980f5366bfeea20a8e099e3a5b864dae9be775842c7a58ca3`,
with installed Filter SHA-256
`9fe3a38f0a27dcd4dc9339f84741eba8a5dfc1cf37b280330a6b2247030fa856`.
Protected operator evidence remains in `local/issue474-20261002/` (native egress
receipt) and `corp-openweb-ui-474-private/` (browser receipt), with a server-side
copy under `/opt/openwebui-upgrade-474/clean-staging/`. The temporary receiver
and its files were removed; connection, Filter flags and model behavior/access
grants were restored. Native grant updates recreate technical row IDs; restore
verification compares the actual resource/principal/permission contract.
The MP3 and cached transcript, paid ledger and all seven production identities
were unchanged. External model and STT provider calls were zero. Long-speech
acceptance was still open at this egress checkpoint; its subsequent acceptance
and the separate manual dictation check are recorded below. No new core diff or
release was applied.

The existing summary and meeting-protocol Prompts were invoked through the native
slash menu and resolved-variable dialog on the owned stored transcript, without
new STT. The protocol preserved all five requested sections, facts and task
owners with no invented deadlines. The summary preserved all four source facts
but returned four bullets rather than the template's five to seven; that exact
format is not marked accepted. Both model results survived reload and another
ordinary user was denied access. Earlier DOCX attempts included an operator
double-Escape clearing the Office selection and native iteration exhaustion;
their failed responses and retained accounting remain in the ledger.
Escape in the composer clears selected tools; dismiss the tools menu by clicking
the editor and verify the selection persists. Use one actual CLI help topic per
call, such as `docx paragraph` or `docx add markdown`; `FORMAT` is a placeholder.

On 2026-10-05 a clean native browser fork of the accepted protocol produced
`474-meeting-protocol.docx` through the model-selected Office skill, help and
create operations. The owner had approved 80 total model requests within the
existing USD8. Only the native staging tool-iteration allowance was raised to
five; the same WebUI image and approved core patch were retained. The six-request
upper bound was reserved before enabling the connection. Independent ZIP/XML
inspection matched all 15 source paragraphs, all 5 native headings and all 9 native
list items, with no extra table/text. The original protocol remained unchanged.
The native Preview tab after reload rendered the source text; the browser's
download matched the server SHA-256
`5f7d0d7ee65af314e40d14d374d52834f8ff1fe6c88a2da486e5e88e2fa7868e`.
Another ordinary user was denied both file and chat access. Provider dispatch was
disabled once the native task completed. Model upper accounting is 46/80; retained
costs/reserves including earlier failures and the previous STT reserve total
USD5.43408004, leaving USD2.56591996. This is conservative operator accounting,
not an invoice. Protected server/local receipts are
`paid-office-protocol-loop-receipt.json` and
`protocol-loop-browser-acceptance-receipt.json`.

An initial browser guard aborted before the application API because it assumed
the old `messages` request shape. The actual 0.11.4 thin browser request uses
`user_message` and native server-owned history. On this Windows/CDP setup,
`postDataJSON()` also exposed mojibake while `postDataBuffer()` matched the raw
CDP bytes and original Russian prompt. Two captures were aborted before the API
with the provider disabled. Correct the observer to parse those actual UTF-8
bytes and verify the native thin request; do not rewrite the request or change
the application. The eventual model run was the first external dispatch for
this case, with no automatic paid retry.

The owner also authorized a separate Lemonfox/STT ceiling of USD5 at USD0.17
per audio hour: about 29h24m42s. The operator caps total audio at 105882 seconds,
preserves the already used 30.696875 seconds and previous reservations, and counts
failed/in-flight work before any fresh dispatch. This grant removes the earlier
two-call/60-second STT limit; it does not raise the model's USD8 ceiling. Use
measured prepared audio and sequential bounded checks, with no automatic paid
retry. The monetary grant is not an instruction to transcribe the whole allowance.

#### Current ordinary-chat acceptance, 2026-10-06

These results supersede the pending states in the earlier dated component
checkpoints. They were exercised with the selected `gpt-5.4-mini`, native tools
and ordinary-user browser controls; no hidden model substitution or second tool
loop was added. Private content, raw requests and tokens stay outside Git.

- DOCX: the native meeting-protocol Prompt produced the source text, OfficeCLI
  created the document, and the latest published document was edited after
  reload. Paragraphs, headings, numbering/styles, source preservation and native
  preview/download checks passed.
- Two-source XLSX: both inputs were read, numeric values 17/23 and total 40 were
  verified independently; editing the latest output after reload produced
  17/25/42 with numeric types and bold headings preserved. Both original inputs
  and the previous result remained unchanged. Wait for loading and select the
  native Preview tab before diagnosing a missing preview.
- Terminal: native model execution and permanent File publication passed, then
  the next edit after reload passed. Recreating Terminal with the same image and
  home volume preserved the old result and the subsequent model edit also
  passed: exact source bytes plus the requested suffix, unchanged source, native
  inline open and separate `attachment=true` download. Separate homes are not
  claimed as complete multiuser isolation.
- Search: native `search_web` returned official Python documentation, then
  `fetch_url` executed on that returned page; the answer and source link survived
  reload. The existing search provider/proxy configuration was retained.
- Long MP4: early Send waited for preparation under the same File ID. One real
  597.9629375-second STT job returned 61 timestamped segments and all 12 declared
  source facts. After STT recreation and model transport recovery, deliberate
  native regeneration reused the stored transcript without another STT job.
  Full original text survives in native content/structured output, with the MP3
  player/download after reload. The regeneration browser request capture is
  missing; native usage/caps, no auxiliary tasks/tools and unchanged STT jobs
  establish the bounded execution, not a claimed wire capture.
- The native summary Prompt initially returned seven bullets with 11/12 facts.
  An explicit ordinary-chat clarification preserved seven bullets and all
  twelve facts, verified after reload. Preserve the first incomplete result;
  this does not establish automatic first-answer completeness.
- Another ordinary user's valid identity/role was checked before and after
  chat/file denials (401/404). An unauthenticated 401 alone is not ownership
  evidence. Short M4A/MP4 and the owner's physical microphone check were already
  accepted; they were not repeated for this report.

On 6 October the owner doubled the model allowance to **240 conservative
request upper bounds within USD16**. The separate STT allowance remains USD5 at
USD0.17/hour; measured usage is 628.6598125 seconds in three historical calls,
with no new STT in this continuation. Earlier request counts and unknown cost
holds remain; this is conservative operator accounting, not an invoice. Reserve
one whole bounded case before enabling the model connection, reconcile actual
native usage afterward and disable dispatch when tasks finish. A failure with
missing usage keeps its full reservation. Qualification caps are test settings,
not product requirements.

PPTX native cloning followed by an explicit ordinary-chat edit of the latest
published result after reload passed on 6 October. Earlier model attempts chose
the old source or reconstructed the slide; later attempts used the correct
latest stored attachment but still reconstructed it. A low-reasoning attempt
through Chat Completions was rejected before any tool call, with missing usage
and its full hold retained. The installed native Responses API route accepted
the same model and low reasoning, then emitted whole-slide copying, but the
five-iteration qualification limit stopped before the mutation's paired tool
output. An emitted call with `status=completed` is not proof of tool execution.
Those initial attempts remain failed. Raising only the native qualification
allowance from five to eight iterations and using the same model with native
Responses/medium reasoning and an 8000-token cap published an exact four-slide
clone, but that first turn reached the cap before changing its heading/final
answer. It remains a partial failed turn, not a successful one-shot request.
After reload, an explicit ordinary request selected that latest stored File
through the native picker without re-upload and changed only slide four's title.
The latter model turn completed without error, including inspection and render.
Independent ZIP/XML verified the unchanged first three slides, layouts/theme and
media, two editable shapes with preserved geometry/styles and one unchanged
embedded image. Source and intermediate files remained unchanged. Native browser
reload/title download matched the final SHA-256
`622904a01e81316c329e14e90e9d9bde0b1eff467f7a048a8de4021c8846ba7a`;
valid-user foreign denials passed. The already completed native render was reused
for independent visual review of the changed fourth slide: readable title/body,
intact picture and no visible clipping/overlap. Original slides have exact
preserved XML and prior accepted source renders; no fresh all-slide render is
claimed. Protected receipts are `paid-pptx-medium-result-receipt.json`,
`paid-pptx-latest-edit-result-receipt.json`, `pptx-latest-browser-acceptance.json`
and `pptx-latest-native-render-receipt.json` under the existing private/ignored
evidence roots.

The latest-edit guard first incorrectly assumed the thin request's whole
`files` list contained only the new attachment. It actually includes distinct
historical chat files; `user_message.files` contained exactly the latest result.
That Send was aborted before the application API, with no new server assistant,
completion log entry or task. The guard was corrected against the exact owned
ancestor IDs, retaining the original full reservation, and the subsequent native
Send reached the model once. No application request was rewritten. Guard failures
are operator evidence, not a platform defect or another paid model attempt.

At this checkpoint all 39 paid batches are terminal, with **177/240** conservative
request upper bounds retained. The USD16 model allowance holds USD8.22299221 and
has USD7.77700779 available, including all earlier unknown holds. No new core
patch/image or production release was made. DOCX/XLSX/Terminal/search/media model
checks and the PPTX route above used the explicitly recorded native qualification
settings; do not claim they all ran on one identical final provider configuration.

For a Responses connection use native `OPENAI_API_CONFIGS[index].api_type =
"responses"`. In the pinned 0.11.4 converter, the Chat parameter
`reasoning_effort` is not renamed; configure it as null and use native model
parameters such as `reasoning: {"effort": "medium"}`, `store: false` and a bounded
`max_tokens`. The native converter maps the cap to `max_output_tokens` and
converts existing function-tool schemas. Installed pure converters were checked
against actual synthetic chat ancestors and current Office OpenAPI before the
paid browser request. This is a narrow configuration qualification, not approval
to change production model routes or an excuse for a new gateway/core patch.

For a deliberately tool-free bounded model check, temporarily disable the
selected workspace model's native `builtin_tools` capability as well as explicit
tools/Terminal and auxiliary tasks. In 0.11.4, empty `tool_ids` alone does not
disable built-in tools. Restore the original capability through the native model
API afterward and verify unchanged resource/principal/permission grants; native
model updates recreate grant row UUIDs/timestamps. Keep provider dispatch disabled
between checks. This qualification setting does not restrict product workflows.

The source checks resolve all six Compose combinations without starting any
containers and exercise the installer on a disposable checkout of the pinned
upstream commit. Eight installer cases cover check-only, exact application,
idempotence, caller `core.autocrlf=true`, and rejection of mixed, foreign,
altered-patch and wrong-commit inputs. Application disables Git line-ending
conversion for that command only; the approved patch hash stays unchanged.
Active CI runs these checks and the existing OfficeCLI/STT suites on Linux.
These checks supplement the live component evidence; they do not replace
ordinary-chat product acceptance or restoration.

Read-only preflight on 2026-10-02 found OpenWebUI 0.9.6 in
`corp-openwebui/openwebui:stt-m4a-d669aec3`, image ID
`sha256:8da17a365a83bde8f999bab94b2a6c497ef733ad9ba44cd655cf87a16fdc2d44`.
The application reported Alembic head `461111b60977`. The host has approximately
8 GiB RAM and 39 GiB free disk; these are observations, not a capacity guarantee.
Heavy clean-staging and later restore/migration checks must run sequentially
under resource limits; do not boot multiple heavy contours simultaneously.

| Material | Observed connection | Restore requirement |
| --- | --- | --- |
| OpenWebUI | Historical full `openwebui_data`, about 16 GiB | Restore ordinary accounts/chats/files/settings with coherent SQLite/WAL; exclude broker data from the target working copy under the 6 October decision |
| STT | `stage2_stt_data`, about 9 MiB | Own SQLite stores and referenced payloads; suspend copied work and cleanup before boot |
| Terminal | Compose-managed home volume, about 332 MiB | Preserve the exact inspected volume identity and permissions; use a separate restored home |
| Runtime | OpenWebUI, STT, OfficeCLI, Terminal and search images | Preserve exact image IDs, deployed source, overlays, mounts, environment and writable-layer differences privately |
| Diagnostics | Host `openwebui-flight-recorder` service | Preserve host history and configure observation of the isolated contour |

Installed Office/STT Filter, Terminal transfer Tool and artifact-workflow Skill
source hashes matched repository revision
`ee736f1e0960e76cf0ed07f88b56512fb57f1203` during this preflight. This is source
parity, not proof of compatibility with the new version.

The current backup script does not produce this complete consistent set. The
first approved cold-copy attempt on 2026-10-02 was aborted because its observed
throughput could not meet the 20-minute window. The same four containers were
restarted after 516 seconds; the partial set is marked `INCOMPLETE` and must not
be used as restoration evidence. No data migration or image switch occurred.
This window is consumed; another production stop requires a new agreed window.

On 2026-10-06 the owner explicitly selected the available **2 October**
`PRESEEDED_UNSEALED` copy for rehearsal, replacing the earlier 4 October request.
The fresh consistent snapshot/downtime decision remains deferred to cutover
preparation. Do not stop production under the consumed first window. The selected
copy is a checked rehearsal source, not a sealed coherent production backup;
its successful core-data restoration does not retroactively change that status.

Before cutover, prepare the fresh consistent saved set after confirming idle
work and obtaining the separate downtime window. Include exact deployed
configuration/source and preserve changed runtime files. Restart the existing
containers after the snapshot; compression and independent copying need not
extend the production downtime. Do not delete existing backups, data or images,
or apply retention during this operation.

Keep a hash-verified independent protected copy off the production disk before
reusing the isolated data copy for migration. A protected operator-workstation
destination with sufficient capacity has been prepared; no complete snapshot
has yet been copied or accepted. Local archive presence, a live-volume tar and
the historical media-only backup are insufficient restoration evidence.

The read-only workstation transfer of both retained October copies was cancelled
after the owner's data-scope clarification. Its partial archive is not an
accepted backup; the server originals remain intact. Archiving the broker corpus
and deleting those old copies are not prerequisites of the revised migration.
The earlier whole-volume capacity estimate does not describe the selected
ordinary working set. A read-only measurement at 20:38 UTC on 6 October found
2,721,419,264 allocated bytes (2.53 GiB) across the retained WebUI, STT and
Terminal data. WebUI accounts for 2,364,067,840 bytes, including 1,494,155,264
bytes of uploads and 510,885,888 bytes of native vectors. STT uses 9,449,472
bytes and Terminal 347,901,952 bytes. These selected roots were not mounted by
any running container. The disk had 762,003,456 bytes free (727 MiB), so another
complete local copy would not fit, even before an operating reserve. Reuse of
the isolated seed still requires the protected independent copy described
above; this observation does not authorize removing old backups or originals.

The 45 unresolved attachments total 684,291 bytes in existing File metadata;
this is an estimate, not a physical payload measurement or a membership
decision. Their payloads remain absent from the selected copy. Final release
capacity remains pending the owner-selected membership, fresh coherent data,
current-data delta and destination. This measurement concerns the Oct2
`PRESEEDED_UNSEALED` rehearsal only, not the final release set.

Before making that target copy, inventory broker membership using existing
paths, file IDs and provenance, without exposing document or chat contents.
Exclude `broker_reports_*` trees and broker-generated/source artifacts from
the target. A path exclusion alone is insufficient: broker files may also be
native uploads or chat attachments. Preserve ordinary accounts, chats, files,
rights and their references; document ambiguous membership before filtering it.
Do not classify by file extension or delete original records. Apply any necessary
reference changes only to the isolated working copy and validate native access
and downloads there. Regenerable caches, temporary files and duplicate backups
are not target user data. The partial filtered rehearsal is described below;
the complete agreed filtered restore has not yet been accepted.

Before booting restored data, remove production addresses from the working
copy's callbacks/connections, suspend copied jobs and cleanup, and prevent
unintended external calls. Preserve the original backup unchanged. Give the
contour its own resources/network and closed access; do not reuse the production
volume names or proxy ports. Historical patches may be used only to prove the
old-version restore. NDFL and Mistral calls remain excluded.

Acceptance requires real restore from the saved set, login, an authorized old
chat/attachment, required results and permission checks. Use an owner-designated
example; do not browse other users' chats for the report. Then migrate this
restored working copy with the installation already qualified on clean staging.
The clean development stand alone is not an accepted user-data migration. On
6 October the separate real-data rehearsal completed with status
`ACTUAL_OWNER_CORE_RESTORE_AND_MIGRATION_VERIFIED`:

- The 16.7 GB original OpenWebUI data copy was mounted as a read-only lower
  filesystem; OverlayFS held all working writes separately. SQLite DB/WAL/SHM
  were copied up, recovered and checkpointed, with integrity checks passing.
  This is an old-data working copy, not a clone of the running old container.
- The exact old image `sha256:8da17a365a83bde8f999bab94b2a6c497ef733ad9ba44cd655cf87a16fdc2d44`
  booted OpenWebUI 0.9.6 at Alembic `461111b60977`. After stopping this isolated
  app and taking a cold SQLite backup of its working DB, the already qualified
  target image `sha256:c4ba3bda7e228f99a246f1d823dfe2a8830dbd8fad6966d2e1862350fb8be423`
  ran the native 0.11.4 migration to `d4c1a8e37b62`.
- All 23 users, 728 chats, 1718 Files, 207 models, 64 Prompts and seven folders
  survived. Exact selected-field comparisons covered roles, password hashes,
  original user settings, model parameters/metadata/prices and saved
  Prompt/Function/Tool content and valves. The native config migration preserved
  `config_old`; all 178 flattened/renamed values matched the installed migration
  exactly. Inspect the actual schema: old `config(id,data)` becomes
  `config(key,value)`; quoted nonexistent SQLite columns can return literals.
- The owner-designated chat retained semantic message content, IDs, graph and
  attachment references. Native browser reload and title-click downloads of both
  actual attachments matched their full sizes/SHA-256 on old and new versions.
  A distinct existing ordinary user's valid authenticated session was checked
  before/after foreign chat/file denials on each version.
- Short-lived controlled native sessions used the preserved signing key and
  existing identities. Original password hashes survived; signing in with the
  owner's original password was not exercised. Native browser timezone and
  unchanged saved chat-parameter writes were allowed only on the working copy;
  message content/graph/File IDs were checked afterward. First-login changelog
  and FileModal title links must be handled through their native controls.
- Original DB/WAL/SHM and the two inspected uploads retained their hashes,
  sizes, inodes and modification/change timestamps; original vector SQLite hash
  was unchanged. All seven production container IDs/images/start/restart values
  remained unchanged. No production stop or paid model/STT call occurred.

Reproduce the isolation: internal Docker network, no published ports/proxy,
explicit resource limits, bounded lifetime, preserved key presence, provider
keys/routes and auxiliary tasks disabled, persistent config disabled and
`SAFE_MODE=true` for copied extensions. Keep optional OAuth encryption keys
absent when absent in the inspected old environment; explicitly empty strings
disable its native fallback to `WEBUI_SECRET_KEY`. Do not generate replacement
production signing/encryption keys to make the restore boot. First vector-store
copy-up exceeded a native connection timeout; a single same-container restart
after copy-up completed succeeded with matching source/working SQLite hashes.
Copy-up delay is the observed working hypothesis, not proof of every timeout's
cause. Preserve initial failed startup evidence alongside the successful proof.

The owned restore containers, network and mounts were removed after validation;
private working upper, cold old DB and receipts remain under
`/opt/openwebui-upgrade-474/owner-native-restore-20261006`. Original secrets,
sessions, chat contents and raw diagnostics are not committed. Copied extensions
were preserved but inactive; their product paths were exercised separately on
clean staging. A separate bounded rehearsal subsequently restored the Oct2
STT store and exact Terminal home volume as private working copies, without
production stops or provider calls. Both the inspected old STT image and the
qualified target image read the same 275 artifact records, 209 edges and
66 transcript-index rows. Every transcript passed the native contract and
content-checksum comparison; the complete table-content digest was unchanged.
The same native policy returned 15 readable transcripts, 50 expired and one
deleted/not-found record on both images. No expiry timestamps were extended or
deleted records revived. Owner-scoped native transcript API reads retained
their original success/expiry results; 15 readable records rejected a different
access context through the native store. These backend access checks complement
the clean-staging product checks; they are not browser acceptance for every
historical transcript.

The pinned Terminal image booted against the separately copied home. Native
health, home listing and execution of a new harmless canary in a dedicated
rehearsal identity passed. All 294 existing files retained their exact bytes;
original ownership and modes survived. This did not replay private customer
commands or claim stronger user isolation than the existing native boundary.
The original STT/Terminal trees retained full content and metadata manifests;
all existing containers retained their identities/images/start/restart values.
Copied provider keys were empty, post-processing/catalog disabled, hard expiry
deletion disabled and the temporary internal network had no published ports.
Temporary containers/network were removed; private copies and aggregate
receipts remain under `/opt/openwebui-upgrade-474/owner-service-restore-20261006`.
The financial corpus was not processed. #516 remains frozen. These historical
restore checks do not prove the newly agreed broker-excluding target copy.
A fresh coherent set of the agreed data, protected independent copy, current-data
delta and agreed rollback after new writes remain release requirements.

At production cutover obtain a fresh consistent snapshot, repeat the rehearsed
migration, and check the changes since rehearsal. Do not deploy the staging DB
with stale or synthetic records. Agree rollback after new writes before opening
production writes; retain both the old compatible set and the new state.

### Issue #474: accounts and code rehearsal, 7 October

The current target is an accounts/code seed, not the older partial chat/file
selection below. A native-schema working copy from the retained Oct2 rehearsal
preserves 23 user rows, 15 auth rows/password hashes, two groups, 207 model
definitions, 64 Prompts with 109 history rows, two Tools, two Skills, 13 Functions
and native configuration. Account/code rows match the source; the three
previously accepted Functions remain active and the frozen broker path remains
inactive. Native resource grants are preserved, except two grants to discarded
shared chats. One pre-existing membership referencing a missing user/group is
omitted; all effective memberships for existing accounts/groups match exactly.
Foreign-key and integrity checks pass. Originals and earlier copies remain
unchanged.

The compact database is 23,162,880 bytes. Chats, files, chat messages, notes,
result folders, jobs and historical artifact tables are empty. No old uploads,
vectors, STT artifacts or Terminal working files were copied. The four qualified
images and unchanged release recipe booted on their own internal network, with
no host ports, empty provider keys and provider flags off. All four services
became healthy. Existing admin/ordinary native signed sessions retained their
roles; the ordinary user was denied admin config export. Native config export
matches the accepted registry installation, including its environment-only
OAuth keys. The ordinary Prompt catalog and accepted Functions were available;
service DNS and the Office callback resolved to this exact new topology.

A new synthetic file uploaded and downloaded through native routes with exact
bytes; another ordinary user was denied access. Native deletion returned the
File count to zero. This proves the backend file lifecycle on the empty seed;
the remaining ordinary browser/provider route is a separate acceptance check.
All four temporary containers, their network and guard were closed; the seed
was retained. All 13 old container identities stayed unchanged. No paid calls
or production changes occurred. Final WebUI allocation was 23,416,832 bytes;
fresh STT/Terminal storage used 4,096/24,576 bytes, with 737,411,072 bytes free.

A cold protected workstation copy of the database, three env files, Compose
inputs and receipts transferred eight files totaling 23,177,402 bytes. SHA-256
and size readback matched; server source metadata stayed unchanged. The parent
and all resulting file ACLs permit only the operator, SYSTEM and Administrators.
The independent database opens with matching account/code counts, empty
chat/file tables, successful integrity and foreign-key checks. This is the
protected rehearsal copy, not a fresh production snapshot.

Those exact eight files were then returned from the protected workstation copy
to a separate restore root. Hashes and sizes matched before rebasing the private
Compose/env paths to that root. The tracked release recipe and the same four
qualified images booted successfully with fresh STT/Terminal directories.
Native account/code/configuration, service DNS, Office callback, file lifecycle
and authorization checks passed on the restored installation. This proves
actual native application recovery from the independent copy, rather than only
SQLite readability or a server-local working copy.

The designated retained owner's original password succeeded through the native
signin API and then the actual browser email/password form. The returned account
and role matched; the browser session survived a reload. No password reset,
account creation, signed-session injection or localStorage injection was used
for this signin check. All retained auth/password hashes stayed unchanged.
Credentials and tokens were used only in memory and were not logged, exported
or included in public evidence. No model/STT requests were dispatched.

The restored four containers, network, guard and dedicated temporary tunnel
were closed; the restored data and protected original copy remain intact. All
13 existing container identities were unchanged. Existing browser contexts and
the main staging tunnel were preserved. Cold integrity/FK and account/code
checks passed after shutdown; the restored database remained 23,162,880 bytes.

For a fresh Terminal bind at `/home`, initialize its empty directory for the
qualified image's native `user` UID/GID (observed 1000:1000) before boot. A
root-owned mode-0700 bind caused a verified permission-denied exit; correcting
only the new empty bind/working directory restored the same container. Do not
copy old homes or make the directory world-writable. Named-volume initialization
and private bind preparation remain the native deployment owner's concern.

The fresh release delta concerns accounts, code and configuration. Historical
chat/file membership is no longer a release gate. Protected current release
data, post-write rollback and separate release/window approval remain required.

The final scoped Responses connection passed one ordinary browser DOCX edit on
7 October. The native catalog selected the restricted connection at index zero
alongside all four preserved source connections. The original 14 paragraphs,
styles and numbering stayed unchanged; only the requested last paragraph changed
in a separate result. Reload, native preview/download, source preservation and
authenticated foreign-user denial passed. The actual assembled request passed
its guard; an additional assertion about stored chat parameters was too strict
and is not reported as passed. The original provider configuration was restored
with dispatch disabled and native tasks empty. No paid retry, STT call, new core
patch or production change occurred.

The owner added 200 model slots: the ceiling is now 440 within the unchanged
USD16 allowance. Historical batch reservations plus this case total an upper
bound of 249, not a measured count of provider requests. The new usage-based
hold is USD0.17090172; total conservative holds are USD8.77721203, including
unknown historical costs. The separate USD5 STT allowance is unchanged. Evidence
is `scoped-route-final-20261007.json` in the existing private operator directory.

### Issue #474: production release accepted, 7 October

The approved release is deployed at `https://gpt.alpha-soft.ru`: the native
version endpoint returns 0.11.4. PR #551 was merged as
`323a3a302929a87cac129ec3c6e6df1b6b1bdc03`; its exact reviewed head
`cc8c1dfd7fd119bbf7261692da0bea552c7fb2de` passed Active CI run 37593190174.
The existing Traefik/TLS router selects the qualified new WebUI; the four
qualified release image IDs and separate volumes are unchanged. The original
four applications are stopped and retained with their original data and copies.
The release window completed in about 30 minutes; measured application downtime
until the public native version endpoint recovered was 638 seconds.

Immediately after stopping old writes, native SQLite backup captured the final
consistent 0.9.6 accounts/code source, including WAL. Five protected files
totaling 23,104,240 bytes were copied off-host and verified by size and SHA-256.
Preserved source fields matched the prepared native migration; only activity
timestamps differed. Password hashes, effective grants, Prompts, Tools and
Skills were checked against this final source. Historical test chats and
attachments were omitted; original old data and backups remain untouched.
The independent protected recovery sets are under the operator's existing
`corp-openweb-ui-474-private/production-release-backup-20261007/`, including
`final-quiesced-source/` and `current-native-0114/`. These contain private data
and are not repository artifacts. Reuse the public model-asset recipe below
when restoring the native target; SQL/env alone are insufficient.

The existing `openwebui-flight-recorder.service` now runs the qualified source
SHA-256 `15f32b01afac4ceae6a35985e4ecb567906a3bdab96768e775d1e9e958c4344d`
with `474-targets.conf`. Its original root/history and resource profile remain.
Fresh resource samples contain all four current application IDs. Original
recorder source/unit/drop-ins are preserved in the protected release directory.
This proves collection, not elimination of every historical overload cause.

One ordinary public browser Send verified original-password form sign-in,
native search, an official Python source, synthetic attachment content,
and persistence of the answer/source/file after reload. The owner confirmed
their ordinary scenario works. All four applications are healthy and database
integrity/FK checks passed. Temporary title/tag/follow-up task settings and the
test task-model override were restored through the native config API; normal
provider enablement remains on. No STT call or repeated Office acceptance suite
was needed at cutover. Budget accounting retains unknown costs: reserved model
slots total 259/440, not measured calls, and conservative holds total
USD9.27434152 within USD16. STT remains a separate USD5 allowance.

After new writes, preserve all new state and repair the new installation first.
An urgent return to the old product requires a separate owner decision; do not
automatically discard new chats/files or feed the 0.11.4 database to 0.9.6.
For later updates, follow the existing pinned-image, isolated-check, backup,
native-migration and route-switch procedure in this runbook. The separately
approved media patch remains an explicit exception with its pinned installer
and removal condition; this release is not an unmodified official image.
Native SearXNG is verified; Brave configuration is preserved but Brave live
acceptance is not claimed. NDFL #516 remains frozen.

### Follow-up: STT cleanup and pinned service builds, 7 October (staging qualified)

The follow-up source removes the STT Filter's obsolete video preparation and
outlet cleanup branch. Filter v0.2.5 requires 0.11.4, consumes ready audio or its
native saved transcript, rejects unprepared media without STT, and skips native
auxiliary tasks. The existing Event Function retains preparation, same-ID
replacement, retry, cleanup and restart recovery. The approved core patch is
unchanged. Production still uses v0.2.4 until this follow-up release is approved
and installed; the original migration acceptance above remains historical evidence.

Office/STT Dockerfiles now pin the existing Python 3.11 base index digest
`sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9`.
Each service's `requirements.lock` records its own resolved production Python
dependencies, including build tools, from the accepted images above. The
different FastAPI versions remain separate. Docker installs the lock first,
then the local package with `--no-build-isolation --no-deps`, followed by
`pip check`; missing/conflicting dependencies fail the build. Standard package
metadata remains the declared compatibility range, while the lock selects the
release. Avoid bare `pip install .` when rebuilding a release.

Debian and Debian-security repositories use the immutable
`20261007T000000Z` snapshot; signed metadata/package hash verification remains
enabled. Only expired snapshot metadata's `Check-Valid-Until` is disabled.
This fixes package selection, not Docker timestamps or bit-identical image IDs.
Registry/PyPI/snapshot availability remains an external build dependency.
Security updates require deliberately advancing the digest/snapshot/locks and
checking the affected artifact; freezing versions is not automatic security upkeep.

Build using the existing service Dockerfiles. Active CI builds both Linux
artifacts and qualifies installed OfficeCLI/dependencies and real offline
MP4/M4A-to-MP3 conversion. It also rejects valid silent video without contacting
a provider. Fresh CI is recorded on the follow-up PR. Component tests do not
replace ordinary-user acceptance after installation.

The server-built artifacts use source revision
`045660d08b31c77fd4947b23c42ecf3a7114af3a`:

- STT: `sha256:ead2a4df9ea157ba1ee2f402c2363b76851dfc1f4609339d7de25dbb7a0a70b8`.
- Office: `sha256:ae3b56ad0634dabd0da9e431282db28aa024f835dad500c91401af134bff0c67`.
- Filter v0.2.5 LF SHA256: `6173fb28481d14ced78e56108385621b7bc08a00c703372e3cd1807f31597b25`.

The release Compose and its existing verifier select these qualified artifacts;
WebUI and Terminal image selections are unchanged. Both image archives and the
current production Function/configuration backup are preserved off-host in
`corp-openweb-ui-474-private/native-debt-release-20261007/`.

Installed STT/dependency/media qualification passed without network access.
Four real OfficeCLI artifact checks passed with the unchanged production profile:
0.5 CPU, 1 GiB RAM, 256 PIDs and a 60-second native command timeout. An initial
operator check using the default 30-second timeout stopped on XLSX range rendering.
The same representative workbook rendered correctly in both old and candidate
images with the working 60-second limit; the candidate crop took 40.115 seconds.
No product timeout/resource setting or test assertion was changed.

On isolated staging, a native password-form session with role `user` uploaded a
10-second MP4 and used one ordinary Send with tools/search/background tasks off.
The same File ID became MP3, source cleanup completed, one STT job ran, and the
short summary plus full cached transcript survived reload. A second valid user
could not access the File or chat. Model usage was 2,920 input / 66 output tokens;
the conservative model hold is USD 0.0032175 and unknown STT cost retains USD 0.01.
Temporary paid-provider access and Filter activation were restored afterwards.
These checks qualify the staged candidate, not an unperformed production release.

Before release, preserve the current Function source/Valves and service image
IDs. Install v0.2.5 through the native Function API, preserving its ID, enablement
and Valves. Any new service images require isolated qualification and an approved
release; these source edits do not switch production. Rollback is the previous
Function source and unchanged Valves plus the previous qualified service images,
preserving all new native chats/files. No schema change or data cleanup is needed.

The public-safe upstream Discussion draft is
[colocated with the exception](../../deploy/openwebui-patches/media-upload-v0.11.4/UPSTREAM_DISCUSSION.md).
It separates the generic handoff/metadata gap from bounded local upload writes;
no upstream PR, publication or maintainer acceptance is claimed.

### Issue #474: historical release preparation, 7 October (completed above)

The following records the preparation state before the accepted release above.
The owner approved the concrete release window of up to 45 minutes, provided
there is no active work. This approval replaces the pending window approval
above. Preparation has not started production downtime: the old four services
remain running; the new four services are stopped with their prepared state
preserved and public routing disabled. Post-write rollback policy still awaits
the owner's answer before opening public writes, as required by the main issue.

A fresh source-compatible account/code seed was captured from the running
0.9.6 source: 23,052,288 bytes, with historical chats, files and corpora omitted.
Ten protected source/configuration/Compose files totaling 23,127,637 bytes were
copied off the host and checked byte-for-byte by SHA-256. The final quiesced
delta is still required; this running-source capture is not its substitute.
Native 0.11.4 migration preserved the scoped source fields and effective grants.
The accepted extension registry, unique new service addresses and scoped
Responses connection were installed through native owners. Original owner
password sign-in passed on this current target without resets or hash changes.

Model assets need their own restore step. The initial native Hugging Face
refresh downloaded unused ONNX/OpenVINO/TF/Rust variants of the configured
`sentence-transformers/all-MiniLM-L6-v2`. Only task-created, unreferenced exports
in the new model cache were removed; original data and backups were untouched.
The new environment sets `RAG_EMBEDDING_MODEL_AUTO_UPDATE=false` and
`RAG_RERANKING_MODEL_AUTO_UPDATE=false`. Native configuration
`rag.embedding_model` and environment `RAG_EMBEDDING_MODEL` both use the existing
supported local path:

```text
/app/backend/data/cache/embedding/models/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41
```

This preserves the exact MiniLM snapshot and weights; it is not a new core
patch or migration of old vectors. For a clean restore, populate that directory
before boot. Use the pinned image's existing Hugging Face download utility with
repository `sentence-transformers/all-MiniLM-L6-v2`, revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, and `allow_patterns` limited to
`config.json`, `config_sentence_transformers.json`, `sentence_bert_config.json`,
`modules.json`, `model.safetensors`, `tokenizer.json`, `tokenizer_config.json`,
`special_tokens_map.json`, `vocab.txt` and `1_Pooling/config.json`. Preserve the
relative file layout. A partial repository cache is not sufficient for the
installed Hugging Face repository-ID resolver, which checks the full snapshot;
the native local-path resolver avoids that requirement. Restoring SQL and the
environment alone does not restore these public model assets.

The installed native local-path resolver and actual CPU embedding forward
(one finite, nonzero 384-dimensional vector) passed with networking disabled.
Actual OpenWebUI 0.11.4 startup then passed on the same prepared volume and
qualified image, after which the new service was stopped. Free host disk was
about 1.65 GB after removal of unused new cache exports. No paid provider call
or production mutation occurred in these checks.

Current native SearXNG preparation preserves the existing search owner and
Brave key. The empty third page was an HTTP 302 with an empty body: the pinned
native loader defaults to `AIOHTTP_CLIENT_ALLOW_REDIRECTS=false`. The new
environment sets this supported option to `true`; the native SSRF-safe connector
remains in use. On the same qualified image, all three original public URLs then
returned content. A single subsequent native search API request returned two
nonempty pages, including the official Python `read_text` documentation. Search
ranking changed to the Python 3.10 URL; an assertion requiring the exact prior
URL failed and is not reported as passed. No repeat search was needed to inspect
and verify the actual response. Configuration and database integrity/FK checks
passed after shutdown. This is native backend evidence; ordinary browser search
on the released route remains to be checked. Brave was not called.
Remaining release steps include the quiesced delta, recorder installation,
merge/CD, public routing and a brief product/owner check.

### Issue #474: historical partial data rehearsal, 6 October (superseded membership)

The owner clarified one mixed-chat exception: retain the ordinary-model message
text, including text about broker attachments, but omit the broker-model turns
and broker attachment descriptors. This is an explicit decision for that chat,
not permission to classify every conversation by its topic. Both native chat
JSON and normalized `chat_message` records were reconciled: eight retained
messages still use `gpt-5.4-nano`; the two broker turns are absent.

An isolated working copy of the selected Oct2 `PRESEEDED_UNSEALED` data now has
449 chats, 1311 native File records, 23 persisted user records and 15 auth
records. These are stored account counts, not active-user counts. There are
1266 selected upload payloads (1,491,447,210 bytes), all copied with independent
SHA-256 readback. The exclusion also covers 93 differently identified files
whose bytes match reviewed broker reports or broker fixtures. Only their new
working copies were removed; source data and old backups remain intact.

The remaining 55 ambiguous references include ten references that already lack
a source native File row. The owner decision therefore concerns 45 existing
files: their working File records are retained, but their payloads have not been
copied. This rehearsal is partial and must not be used as the final release set.

On 7 October the owner separately authorized removal of only this superseded
rehearsal's unused `native-data/uploads` directory. Its 1,494,155,264 allocated
bytes were removed after checking mounts of all 39 containers, including stopped
ones. All container identities, states and restart counts stayed unchanged. The
parent database/code, production source data, original archives and protected
account/code backup remain. The partial rehearsal's upload payloads are therefore
no longer replayable. Free space rose to 2,200,666,112 bytes at that checkpoint;
this is not acceptance of unrestricted production capacity.

The pinned `c4ba3bda` image performed the native 0.9.6 -> 0.11.4 migration in an
internal network with no published ports, empty provider keys and SAFE_MODE.
Accounts/password hashes, model definitions/prices, prompts, folders, grants,
tool/function source and all 178 native config values/history were verified.
Expected working-copy changes were limited to native schema additions,
authenticated-user activity timestamps, SAFE_MODE function deactivation and
native browser timezone/tool-permission metadata. The previously implicit
default tool permission is recorded by the new UI; message text/ancestry and
attachment identities are preserved.

Ordinary-user browser checks opened the designated old chat and mixed ordinary
chat after reload, downloaded both designated attachments through native
controls with exact source hashes and rejected an authenticated different user.
These checks used short-lived native signed sessions; original-password signin
is still unverified. No model/STT calls or production changes occurred.

The native vector selection contains 477 agreed ordinary collections; 45
collections linked to ambiguous attachments await the same owner decision.
The copied native index was pruned through `delete_collection`, retaining the
existing ordinary segment IDs/graphs. All selected collection/segment/embedding
and embedding-metadata SQL records match the source. The 297 excluded or
regenerable collections, their queue topics and 296 leftover segment directories
are absent; both working SQLite databases were compacted and integrity checked.
Five native search samples passed, including the exact source-query regression.
These backend checks reuse existing vectors and make no embedding-provider call;
they do not claim a paid browser RAG route. A separate API rebuild was rejected
because its native search differed despite matching readback records; its failed
evidence was retained rather than reported as successful.

Earlier whole-corpus and service restore evidence does not establish acceptance
of this new partial set. Fresh coherent release data, a protected independent
copy, current-data delta, original-password signin, final topology/recorder checks
and separately approved cutover remain required.

### Issue #474: final shared model route, 6 October

The affected DOCX, XLSX, Terminal, search and full-transcript continuation were
checked through ordinary browser chats using the same pinned artifacts and
`gpt-5.4-mini`, native Responses, medium reasoning, an 8000-token output cap and
eight native tool-loop iterations. The previously accepted final PPTX clone/edit
already used this configuration and was not repeated. This is qualification of
the selected staging route, not a change to every production model/provider.

- DOCX changed only the requested last paragraph; the other 14 paragraphs,
  styles and numbering were preserved. XLSX retained numeric 17/26/43, bold
  headers and all other cells/styles. Both used the latest existing native File,
  produced a separate result, and passed native preview, exact download and reload.
- Terminal staged the selected source, ran the requested edit and published
  exactly the original bytes plus the requested suffix. Native inline opening,
  attachment download and reload passed. Sources remained unchanged.
- Search acceptance requires a nonempty returned list and fetching a URL from
  that list. The first check returned `[]` and then fetched a known official URL;
  its original verifier conclusion was corrected and retained as failed. The
  next query returned results without the required official source and remained
  failed. A representative preflight through the actual native ordinary-user
  search API preceded the final paid check. That check found the official Python
  pathlib page, fetched the returned URL and answered correctly with its link;
  reload and a valid foreign-user denial passed. Direct SearXNG output alone is
  not qualification of the native model's result list.
- The final full-transcript continuation produced exactly seven bullets with all
  twelve source agreements, checked individually against the original text, and
  no additional facts. The exact complete transcript remained in native ancestry.
  Reload passed; the STT store hash and job count were unchanged. This was a plain
  continuation of the existing accepted Prompt/source, with no new upload, STT
  call, cache-inlet dispatch or fresh slash-picker acceptance claim.
- Valid distinct-user identities and denied access were checked for each chat
  and, for file cases, each result. Browser checks made no model/STT requests.

The 0.11.4 browser sends chat/parent references; the server assembles history.
Native `body.files` retains saved chat files only while they are referenced in
history, then adds current non-image attachments and deduplicates. It is not
every assistant-published ancestor file. Two overly strict operator guards
stopped requests before the application API; absent server messages, unchanged
parents, empty tasks and absent completion logs proved zero provider calls.
Original abort receipts were kept, then the qualified native Send reused its
existing reservation without rewriting the request or changing product code.

All 46 paid batches are terminal. The conservative model bound is **240/240**;
the USD16 allowance holds **USD8.60631031**, with **USD7.39368969** available.
These figures include earlier unknown-cost holds and are not an invoice. The
separate USD5 STT allowance and three historical STT jobs remain unchanged;
there were no new STT calls in this continuation. Model dispatch and the STT
Filter are disabled between checks; native tasks are empty. Protected final
evidence is `shared-final-route-acceptance.json` in the existing operator/server
evidence directories. Do not rerun paid checks after the count ceiling.

### Issue #474: separate release recipe, prepared but not deployed

[`openwebui.staging-release-0114.compose.yml`](../../compose/openwebui.staging-release-0114.compose.yml)
declares the four new application services, qualified immutable images and new
`openwebui-0114_{data,stt_data,terminal_home}` volumes. It has no legacy loader
mounts, STT read of the WebUI SQLite volume, automatic build/pull or host ports.
The current Traefik/TLS, SearXNG/Valkey and proxy remain their existing owners.
The service network permits the existing Terminal egress behavior; this does
not strengthen the agreed trusted-team isolation boundary.

Private env files preserve the actual runtime values, including signing keys,
provider/storage/TTL settings and the absence of optional OAuth keys. The
required `RELEASE_WEBUI_NO_PROXY` and `RELEASE_STT_NO_PROXY` values preserve each
service's actual exclusions and append its new service names; do not replace
custom storage/internal-domain exclusions with only the staging list. The
`format: raw` env input prevents a second interpolation of literal `$` values.
An isolated synthetic native Compose create/inspect check proved the exact
runtime value; that container was never started and was removed. No actual
secret was printed. The release validator resolves both Compose forms without
starting services; server inspection also confirmed every pinned local image.
The four-service recipe was also booted in a bounded private rehearsal on the
partial Oct2 selection. Production routing and fresh-data acceptance remain open.

The 6 October rehearsal used the exact `d8410533` recipe (`29b4702d` SHA prefix)
and the four qualified images, with an operational overlay that suspended
providers/old Functions, removed the external network and host ports, disabled
automatic restarts and limited log growth. Only native `webui.db` and its WAL/SHM,
uploads, vector index and cache were moved within the existing working copy into
`native-data/`; file hashes/inodes were preserved. Env files, tokens and proof
controls remain outside the application data mount. STT and Terminal use their
already selected private contexts, without another full data copy.

All four services became healthy without OOM/restarts. The WebUI resolved each
new service name to its exact new container, and OfficeCLI's actual help request
validated an ordinary user's session through the new WebUI callback; an invalid
forwarded session was rejected. The existing staging recorder sampled all four
exact new IDs without another recorder or history root. Its selected log/event
targets were not changed; their final release qualification remains pending.

Native browser opening/reload of both retained chats, both designated downloads
and valid foreign-user denials passed on this topology. STT's database and all
294 existing Terminal files retained their hashes, owners and permissions after
boot. This was not another model tool-loop or transcription test, original
password signin, external provider/search-route proof or full filtered-set
acceptance. The 45 shared files remain pending. The four temporary containers,
internal network and bounded guard were closed; the native working data remains
available at its recorded private path. All 13 existing production/main-stage
container identities and restart counts stayed unchanged. No paid calls occurred.

The initial operator create selected an earlier server recipe lacking the new
STT address; it was rejected before startup. The recorded latest source hash,
resolved values and actual container env were reconciled before boot. A dated
server directory or older validation receipt is not the release source identity.

The recipe proposes the already qualified eight-iteration native tool cap;
prices and model definitions are preserved. Review this setting with the release.
For the selected `gpt-5.4-mini`, a scoped native Responses connection can be
prepended with `model_ids: ["gpt-5.4-mini"]` and no prefix, reusing the current
OpenAI URL/key. Move every original URL/key/config entry together by one index
without changing its values. The pinned native catalog keeps the first matching
model ID, preserving other models' original protocols and the selected public ID.
The existing `/openai/config/update` clears its native model caches; use that
owner and check numeric config keys rather than silently losing legacy keys.
A provider-disabled API trial accepted/read back the exact five-entry config,
preserved models and all other exported settings, then restored the original
stand config. An offline installed-code probe checked the selection rule. Actual
ordinary-user model dispatch on this profile remains pending, and this is not
qualification of every preserved provider/model. Change only the selected
Workspace Model's qualified parameters; do not copy fixture global/user defaults.
Check the actual saved-chat request before dispatch: a null model default does
not remove an explicitly supplied legacy `reasoning_effort` parameter.

The scoped native connections change their service addresses:
Office server `officecli` to `http://officecli-0114:8080`, Terminal `office-linux`
to `http://open-terminal-0114:8000`; Office callback already points at
`http://openwebui-0114:8080`. Preserve Session auth, native chat/message custom
headers, API keys, access grants and the transfer Tool's native local callback.
The Media Event Function v0.1.2 reads `STAGE2_STT_BASE_URL`; its default remains
`http://stage2-stt:8080` for the existing stand. The release recipe sets the
unique `http://stage2-stt-0114:8080` address. Set the existing STT Filter's native
`sidecar_base_url` Valve to the same address, preserving its remaining settings.
The new STT has no `stage2-stt` alias, so isolated preflight does not require
stopping old STT to avoid two DNS owners. Check memory/disk headroom and suspend
copied providers/tasks before booting a private working set. This setting changes
only our registered extension; the approved upstream bridge/image are unchanged.
Production stop/cutover still requires its separate approval. Rollback stops all
four new services before the retained old application set resumes.

When overriding the preparation address on a stand, preserve its current
`NO_PROXY`/`no_proxy` exclusions and append the selected internal hostname.
On 6 October, v0.1.2 was installed through the native Function API and only the
stand WebUI was recreated on the same qualified image. A normal user's native
file input prepared a one-second M4A tone through a unique STT container name,
showing the resulting MP3 before Send with the same File ID. Downloaded bytes
matched native size/SHA, independent FFprobe confirmed MP3 audio, and a second
valid ordinary user received HTTP404 for metadata and content. Source/pending
paths cleared, the source fixture and ledger stayed unchanged, and all five
other stand and seven production containers remained unchanged. No model or
transcription provider was called. This qualifies the configurable preparation
address; fresh data, whole release topology and the final model route remain
separate checks.

The accepted native registry was also installed on that partial working set,
then checked after an intentional WebUI restart. Office Filter, Terminal Tool
and Artifact Workflow Skill already matched the qualified sources after LF
normalization; their original settings and grants were retained. Only the STT
Filter source/service Valve needed updating, and the Media Event Function needed
adding. Native tool/terminal configuration kept the original IDs, authentication,
keys and grants while selecting the unique new service addresses and Office chat
and message headers. The other Functions remained untouched and inactive; frozen
broker code was neither loaded nor invoked.

On pinned 0.11.4, `open_webui.models.config.Config.upsert` persists settings only
when persistent configuration is enabled. API writes with persistence disabled
update in-memory defaults and do not qualify a durable install. Before booting
the restored copy with persistence enabled, use the native Config model owner
on the cold working copy, with database migrations disabled, original WebUI
secret and no network, to suspend only `openai.enable` and `ollama.enable`.
Do not import another application or edit production data. Confirm all copied
Functions are inactive, keep provider keys unavailable and isolate the network;
then install the approved extension/configuration through native admin APIs.
`SAFE_MODE=true` deactivates Functions at startup, so it cannot be used to prove
that their enabled state survives restart. Reconcile the copied inactive registry
before the bounded normal-mode rehearsal. Preserve the private original settings
and registry for comparison and rollback.

The native persistent startup renamed 63 `rag.web.*` settings to `web.*` without
changing their values and seeded missing defaults. Verify the native mapping
rather than recreating obsolete keys; OAuth settings can remain environment-owned
and appear in export without corresponding persisted rows. The complete installed
config/Function/Tool/Skill state survived restart and matched the cold copy after
shutdown. A real existing ordinary account used the native file picker: the same
File became a completed MP3 in one preparation attempt. Bytes, hash, size, MIME,
actual codec and a distinct valid foreign user's metadata/download denial passed.
Office help accepted that ordinary native session through the new WebUI callback
and rejected an invalid session. The synthetic File was removed through its native
API after verification. No Send, model, transcription or embedding call occurred;
the STT artifact-store hash and all 13 previous container identities were preserved.
The owned four-service candidate, internal network, guard and tunnel were closed,
with the installed working data retained. This is not original-password login,
fresh-data, external-provider-route or whole release acceptance.

The existing staging recorder was subsequently selected to observe the four
actual new targets, retaining its six old targets, root/history/cursors and single
writer. Exact IDs in start/stop events, native HTTP access logs and fresh resource
samples passed. The original source delivered stop events with up to 141.024
seconds of delay under staging limits of 128 MiB / 5% CPU; its first long-lived
process stop hit the native 90-second timeout. The timeout cause remains unproven.

A measured one-line atomic JSON encoding improvement retained flush/fsync,
replace, file format and privacy/retention semantics. On 779 actual diagnostic
rows and 12 events, differential native Store replay produced byte-identical
cards and reduced profiled CPU time from 30.34 to 3.14 seconds. Candidate source
SHA-256 is `1ae147e06dc3c48c37d1bac64469ffe93190262a2fd6a1d5aa8ce6bf854c9da0`.
Ten native tests passed separately. The prepared Active CI addition could not be
published because GitHub rejected workflow updates without the OAuth `workflow`
scope at that trial. The proposal was subsequently published through the
existing GitHub connection on 7 October; Active CI now includes recorder tests.

A bounded live trial used that separate source file in the same staging unit
and root, leaving the shared installed source and production recorder untouched.
All four healthy qualified services produced start/access/resource evidence;
maximum start delay was 0.119 seconds and stop delay 87.907 seconds. All twelve
stop cards completed with exact full before/after windows against native history,
zero omitted rows and no buffer overflow. No collector OOM occurred, but memory
limit hits and CPU throttling remained. This is a partial improvement, not
latency/capacity acceptance or long-running fault closure.

The candidate writer stopped normally, the original staging source/unit/targets
were restored with fresh collection, and all owned applications/network/guard
were closed. Cold native config and registry matched the accepted installation;
all thirteen prior container identities/restarts and the production recorder
unit/PID remained unchanged. Working data was retained and no paid calls made.
See the [recorder operations instructions](../infra-ops/openwebui-flight-recorder.md)
for the scoped update/rollback procedure. Production source/target installation
still requires the separately approved release and final qualification.

A follow-up targeted change removed per-event refresh of every pending card.
Each new event immediately fills its own card; all pending cards still refresh
and complete in the existing sampling cycle. SHA-256 source:
`15f32b01afac4ceae6a35985e4ecb567906a3bdab96768e775d1e9e958c4344d`.
The same actual-row differential replay retained byte-identical completed cards
and reduced profiled CPU further from 3.20 to 0.86 seconds. Eleven native tests
passed both locally and on the host, including a twelve-event burst with immediate
before history, durable restart and complete before/after windows.

Under the same staging 128 MiB / 5% CPU limits, a second actual four-service trial
observed all start/access/resource identities and all twelve stop events. Maximum
start delay was 1.458 seconds; maximum delay across the entire twelve-stop-event
set was 20.469 seconds. The early four-identity observation was 13.184 seconds
and is not the complete-event maximum. All twelve cards completed with exact full
windows against native history, no omitted rows and no buffer overflow. The writer
stopped normally, original staging source/unit/root/targets were restored, owned
temporary resources were closed and cold config/registry matched. All thirteen
old containers and the production recorder remained untouched; no paid calls.
Memory limit hits persisted without OOM, so long-running headroom is not claimed.
The published workflow inclusion covers eleven tests. Final production target/resource
qualification remains part of the separately approved release.

The same published recorder source then passed a bounded four-service trial
with the production recorder's observed resource/stop profile: 192 MiB, 10% CPU,
128 tasks and TimeoutStopSec=5s. Actual staging properties matched those read
from production. Maximum delay across all twelve stop events was 7.132 seconds;
all twelve cards completed with exact full before/after history and no omissions.
Memory peaked at 138.875 MiB with zero memory/pids limit hits, OOM or swap.
Collector stop returned native Result=success; the measured stop-command duration
was 0.282 seconds, within the configured five-second deadline.

The original staging source/unit/targets/root were restored with fresh collection,
owned temporary applications/network/guard closed and cold native config/registry
preserved. All thirteen old container identities and the production recorder
unit/PID/source stayed unchanged; no paid calls. This accepts the bounded
lifecycle on the actual production resource profile, not sustained-load capacity,
complete production unit hardening or installation in production. The original
long-lived writer timeout cause remains unproven. Final source/target installation
still belongs to the separately approved release.

Snapshot/migration/release sequence, after separate approval:

1. Recheck idle work, current identities, free space and actual deployed
   env/source/mounts. Prepare the agreed accounts/code seed and a protected
   off-disk destination. Preserve account/password/role/right and integration
   semantics; historical chats/files/vectors/service artifacts are excluded.
   The Oct2 rehearsal data is not current release data.
   Estimate the cold delta before requesting a bounded stop window. Abort and
   resume the same old containers if the agreed window cannot be met.
2. In the separately approved window, stop only the four old application
   containers and capture the coherent selected account/code/configuration
   delta, including committed SQLite WAL state. Keep old chats, STT payloads,
   Terminal homes and existing backups intact on the old side. Search, Traefik
   and proxy stay running. Seal hashes and an independent protected copy before
   migrating the selected working set; do not archive the discarded corpus as a
   prerequisite of this migration.
3. Boot the fresh working set using the qualified image and native migration.
   Suspend copied work/providers/extensions initially; preserve backup records,
   verify the broker exclusion, then replace/disable only the owned obsolete
   extension connections, removed response-to-DOCX Action and old loader/Prompt
   catalog path. Keep #516 frozen; preserve its source and the existing private
   #525 archive without enabling broker processing.
   Install the accepted Tool/Skill/Filters/Event through native owners. Reconcile
   the exact IDs and source hashes with the fresh registry; do not bulk-delete it.
4. Check current account/code deltas, native settings/models/prices, owner
   password login, new allowed test chats/files, service callback/DNS and ordinary product
   routes. A staging-only Responses setting does not authorize blanket changes
   to preserved production connections, user params or 207 model definitions.
5. Update the existing host recorder's explicit targets to the new four generated
   Compose names, retaining its root/history and current old targets for rollback.
   Verify collection from the new identities. Do not start another writer on the
   same root. Rollback restores the previous selector, not the diagnostic history.
6. Apply [`openwebui.staging-release-0114.route.compose.yml`](../../compose/openwebui.staging-release-0114.route.compose.yml)
   only after the accepted fresh migration and approved cutover. It reuses the
   existing `openwebui` Traefik router/TLS owner; the old WebUI must already be
   stopped. Keep production writes closed until owner checks pass.
7. Before new production writes, rollback stops the candidate and restarts the
   retained old containers/volumes/config. After any new writes, first preserve
   the complete new state and reconcile its delta; do not attach a migrated
   SQLite database to 0.9.6 or silently discard new chats/files. Agree this
   consequence with the owner before reopening writes.

The recipe is reviewable source preparation, not permission to stop, merge,
deploy or switch the product. Off-disk account/code restoration and original
password login passed on 7 October. Fresh protected release data/current delta,
post-write rollback agreement and release/window approval remain open.

### Older production restoration recipe

1. Остановить сервисы:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml down
```

2. Восстановить `.env` из server-local backup и выставить права:

```bash
cp /opt/backups/openwebui-prd0/env-<timestamp>.backup .env
chmod 600 .env
```

3. Восстановить `openwebui_data` по инструкции [../../scripts/restore.md](../../scripts/restore.md). Это восстанавливает пользователей, историю и настройки OpenWebUI, включая provider connections, сохраненные через Admin UI.

4. Для `traefik_letsencrypt` выбрать один путь:

- штатно не восстанавливать volume и дать Traefik перевыпустить сертификат через Let's Encrypt, если DNS и порт `80/tcp` доступны;
- восстановить volume по [../../scripts/restore.md](../../scripts/restore.md), если нужно сохранить ACME account/certificate state.

5. Запустить сервисы:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

6. Проверить strict TLS, hardening, вход администратора, provider connections, историю чатов и новый запрос к модели:

```bash
bash scripts/network-hardening-check.sh
bash scripts/smoke-test.sh --strict-tls
```

## Важно

Backup содержит секреты, если копируется `.env`, и может содержать provider secrets в `openwebui_data`. Не переносить такие архивы в Git, публичные чаты или незащищенные хранилища.

## DOC29 canonical-store verification

Broker Reports canonical metadata and payloads are expected below the existing
`openwebui_data` mount. A backup/restore run is accepted for DOC28 only when a
safe receipt proves all of the following on the approved target deployment:

- metadata and payload manifests match before backup and after restore;
- every sampled active pointer resolves to the same canonical root hash;
- every referenced chunk is readable under the same tenant/access context;
- rollback targets still resolve after restart;
- no private bytes, paths, filenames, secrets, or payloads enter Git evidence.

On 2026-08-05 an isolated coordinated drill passed with 172 payload files,
16/16 active pointers/root hashes, 0 missing chunks and fail-closed access. A
target pre-change SQLite snapshot outside `openwebui_data` also passed
`integrity_check=ok`. The target restore drill was not run because the bounded
backfill made the host control plane unresponsive. Therefore target
`BACKUP_RESTORE=NOT_CONFIRMED`; the isolated PASS must not be promoted to a
target claim.

## DOC30 target status

DOC30 recovered SSH and proved current Broker and STT integrity. DOC29 wrote no
canonical state, so the evidence-bound recovery action was `RETAIN`; the
historical pre-change backup was not restored. The resource-bounded target run
then stopped at an XLSX container OOM after 8 of 16 active versions.

No new complete DOC30 backup or isolated restore is accepted because complete
backfill and restart/recreation proof were not reached. Therefore target
`BACKUP_RESTORE=BLOCKED_BACKFILL_INCOMPLETE`. Do not promote the historical
snapshot or isolated DOC29 drill to current target proof, and never restore or
delete STT data without separate integrity evidence.
