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
Proven backup/restore and fresh data migration remain required before cutover.
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
its worst-case cost reservation and is not accepted; the remaining Office,
Terminal, search, STT and restoration scenarios still require qualification.

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
acceptance remains open; the separate manual dictation acceptance is recorded
above. No new core diff or release was applied.

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
| OpenWebUI | `openwebui_data`, about 16 GiB | SQLite with WAL, uploads, settings, extensions and retained Broker data |
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

On 2026-10-05 the owner clarified the rehearsal data cutoff as **4 October**
(the earlier reference to 4 September was corrected) and deferred the fresh
consistent snapshot/downtime decision until cutover preparation. Do not stop
production under the consumed first window. Establish the exact available source
and its consistency before treating it as a historical saved set: neither the
date correction nor `PRESEEDED_UNSEALED` proves a 4 October snapshot. Rehearsal
data and proof of production rollback remain distinct.

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
The clean development stand is not an accepted user-data migration. Current status:
`RESTORE_NOT_YET_VALIDATED`.

At production cutover obtain a fresh consistent snapshot, repeat the rehearsed
migration, and check the changes since rehearsal. Do not deploy the staging DB
with stale or synthetic records. Agree rollback after new writes before opening
production writes; retain both the old compatible set and the new state.

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
