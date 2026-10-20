# Shared native media context

Date: 20 October 2026. Status: implementation, component qualification, native
Function installation and bounded ordinary-user workflow checks passed.
Independent final review passed; repository delivery is tracked in PR #572.

## Accepted outcome and owners

Every user selects an ordinary chat model and uploads multimedia. The first
result contains a short summary and the full speaker/timestamp protocol.
The operator explicitly confirmed that an upload accompanied by a task still
returns these two parts first; tasks are performed in following messages.
The same saved source must remain available after reload, regeneration and
model switches, without repeated STT, duplicate injected sources or silent cuts.

| Meaning / boundary | Existing owner | Consumer |
| --- | --- | --- |
| Upload/preparation/File identity | Native Event, File and Storage | Existing STT Filter |
| Recognition, segments, provider | Existing stage2-stt/Lemonfox | File transcript cache |
| Canonical timed/speaker protocol | File `stage2_audio_context_filter.display_transcript` | First visible result and each subsequent model request |
| Selected branch and compacted history | Native Chats/ChatMessage and compactor | Filter reads raw branch only for File scope/provenance; outgoing history remains compacted |
| Summary and subsequent tasks | User-selected ordinary model | Native content/output rendering |

No new service, store, Pipe, provider client, core patch or model/user allowlist
is introduced. Existing preparation and direct-size-error semantics are retained.
The [preceding audit](CHAT_STYLE_CONTEXT_AUDIT.report.md) records the observed gap.

## Native options and chosen scope

The installed OpenWebUI 0.12.2 source was inspected before implementation.
The [documented Filter surface](https://docs.openwebui.com/features/extensibility/plugin/functions/filter/)
provides request and result adaptation; the deployed version was checked rather
than assuming that current documentation describes this installation exactly.

`retrieval/utils.py:1495` supports full native `File.data.content` without
indexing, including audio MIME, but `middleware.py:3331` gates that automatic
path on model `file_context`. The native Sources panel persists separately from
assistant replay, but is gated on `citations`; its compiled SourceModal initially
previews 10,000 characters with an explicit expansion control. There is no native
display-only flag for inline `output_text`: `misc.py:502` replays all such parts.

Chosen adaptation: retain the current two-part inline display, use the existing
global Filter to restore canonical File sources, and remove only the verified
managed protocol copy from outgoing assistant history. Raw selected history is
never substituted for the already compacted request. Exact matching is scoped
by linked File and ordered message occurrences; ambiguous matches are retained.

## Implementation slices and checks

1. Protocol formatting preserves every nonempty segment, words/order and known
   timing, including mixed/missing speaker IDs and invalid numeric timestamps.
   Unknown speakers are labelled, not invented. Plain legacy caches still work.
2. Filter admission separates current uploads from historical sources. All current
   recordings are processed; old sources are read from owner-scoped File cache.
   Missing cache and partial failures are explicit; historical media never
   causes an automatic paid STT retry. Non-media attachments remain native.
3. A single complete source block is passed to the selected model. The recorded
   words are data, not user instructions; conditions/proposals must not become
   invented commitments. Exact source-wrapper cleanup preserves unrelated
   authored text, native annotations, tools, reasoning and stored messages.
4. The first result remains summary plus full protocol in both content/output.
   Failure notices precede the protocol, so a later request can remove its exact
   managed suffix without removing the notice or duplicating the good source.

All **187** STT behavior checks passed, including regression cases for
unlinked identical authored quotations, split output text and the partial-error
transition. Independent implementation review passed for the candidate.

Offline qualification uses the exact installed WebUI image with fresh synthetic
SQLite/File/Chat/ChatMessage/Storage, read-only source mounts and no network.
It reuses the installed branch/output-conversion functions, extracted unchanged
to avoid starting the application. It proves persistence/reload, model rename,
branch isolation, compacted-request preservation, File ownership, auxiliary no-op
and unchanged cached File bytes/data. The fresh-source case uses only an HTTP
fixture in place of the external STT service; it is not paid recognition.
Both cached and fresh-source qualification passed in installed image
`sha256:a0f5752afafd24ae065190ef28d88717e9a29c739ccb23be1e2d3e7ff7bfe424`.
Candidate Filter v0.3.0 LF SHA-256:
`1cc93503c4b201048712e99c673b0a628e46559c1ec45ac0478c8ede1bb170cc`.
The fresh case made one HTTP-fixture transcription call; external provider calls
were zero. The private receipt is
`/tmp/codex-media-context-20261020/native-context-runtime.final.log` on the VPS.

A separate representation rehearsal used the actual private problematic-chat
snapshot. The 11,673-character canonical protocol was restored once, excluded
from outgoing assistant history, and produced the identical source-context hash
for three model labels. This proves input assembly, not real model compliance.

## Native installation and product acceptance

[PR #572](https://github.com/Kwentin3/corp-openweb-ui/pull/572) candidate
`43393d77e25632d2438238c6f5f6f60201b805ee` passed
[Active CI](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/39424058914).
At 15:44:35 Moscow time on 20 October the Filter was updated through the native
Function API after checking there were no active chat tasks. Source readback
matched the qualified LF hash; owner, activation/global flags and Valves remained
unchanged. No Event, core, image, service restart or other Function changed.
The rollback backup is private, mode 0600, at
`/root/codex-media-context-20261020/stage2_audio_context_filter-before.private.json`.

A separate ordinary account signed in through the password form and uploaded
the real 6,844,652-byte source through the file input. Its new native File
completed preparation in one attempt, with no transcript before Send.
After separate approval for one STT and three bounded short answers, the
ordinary account sent the uploaded file with an explicit request for a letter.
The first Gemini Flash response nevertheless contained the required short
summary and complete protocol. Both headings survived reload; persisted
`content` and flattened native `output` were equal. The 14,005-character protocol
appeared once as the exact managed suffix, with 145 timestamped segments through
14:15; plain recognition text contained 10,381 characters. Canonical protocol
SHA-256: `70863e572d3cdcb71a9c7d8c78175f5a9a8160ceb2c59f00a0958e995dc282b8`.

The user then switched through the native model picker from
`models/gemini-3.5-flash` to `models/gemini-3.5-flash-lite`, requested a short
business letter, and used native regeneration. Both later responses completed
without adding a second displayed protocol. After another reload the File cache
JSON and `updated_at=1792500663` remained byte-for-byte/value identical.
The browser gate accepted exactly three main requests (15:50:37, 15:54:34,
15:55:15 Moscow time), then closed. Auxiliary generation and tools were disabled,
and output was limited to 512 tokens per request. This is bounded tool-free
ordinary-route acceptance, not acceptance of external tools or every provider.
Native usage was not returned; estimated tariff cost is not an invoice.

Safe browser evidence is retained in ignored
`local/media-context-20261020/browser-product.safe.json`; the test chat is
`f6b17de1-4701-47cf-a17b-e9fc436a02ff`, its File is
`41ba7572-b3ef-4c5c-8869-7f3eb263abe8`. Private text/screenshots remain private.
Server-side read-only accounting independently found exactly one STT job and one
transcript result for this test user, scoped to this exact chat/File; the service
log also showed only one successful transcription POST during the acceptance
interval. The canonical protocol equals a fresh render of all 145 provider
segments (reported duration 855.4666875 seconds), without skipped segments.
The independent R1-R5 review passed the workflow/context scope with the model
quality limitations below. Its safe receipt is retained in ignored
`local/media-context-20261020/product-review.safe.json`.

The original customer's source File `261f0c31-5408-49b3-84ac-0ee5f0912914`
retained its original 6,844,652 bytes, SHA-256
`a8081c8fc5506519fe9c9e7d96b1c8b849db24bd2c7b53b01e14bf20a8de75d2`,
cache hashes and `updated_at=1792496203`. The customer edited their original
chat during the audit; whole-chat immutability is not claimed.
The test account was returned to `pending`, its sessions revoked, and the old
token received HTTP 401 for its File. Its chat/File remain for private review;
the isolated browser context was closed. The original two browser tabs remained.

Final read-only service checks confirmed both existing WebUI/STT images,
15 October start times, zero restarts and healthy status. STT image:
`sha256:ead2a4df9ea157ba1ee2f402c2363b76851dfc1f4609339d7de25dbb7a0a70b8`.
Installed Filter readback remained the qualified LF hash, active and global.

Semantic inspection confirms that the summary identifies the discussion as
discussion/proposals, and the letters preserve the key accounting causes,
consulting-versus-bookkeeping responsibility, and proposed corrective work.
There are still model errors: the second response omitted the separate-payment
condition (regeneration restored it), and both letters introduced shift-closing
wording where the recognized source contains an unclear word after "closing".
Neither "shift" nor "month" can be established from that text alone. These are not missing
source bytes; all source text remained available. Perfect generation accuracy
is not established or promised by the context repair.

## Limitations

No source truncation or hidden summarization is added. Native compaction occurs
before inlet; the full File source is restored independently of the compacted
conversation. The installed framework has no universal model-window getter or
exact tokenizer: native compaction estimates tokens and its threshold is not a
provider window. An oversized source must receive an explicit provider/native
error; universal fit in every model is not claimed. A real provider-window-limit
failure was not induced. Full-recording word-for-word audio accuracy was not
independently audited. Live model compliance was checked only in the stated scope.

Raw customer text, private snapshots and runtime receipts remain in ignored
local evidence or the private task directory on the server. Public source
contains only synthetic test material and sanitized evidence descriptions.
