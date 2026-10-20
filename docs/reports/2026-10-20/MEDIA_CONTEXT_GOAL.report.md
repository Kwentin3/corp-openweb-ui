# Shared native media context

Date: 20 October 2026. Status: candidate implementation and component qualification;
production/browser acceptance is not yet complete.

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

## Remaining product acceptance and limitations

Ordinary-user first upload, reload, follow-up tasks and model switching remain
to be checked after CI and native Function release. Paid provider calls require
their own bounded operator approval; the earlier PR #570 approval is not reused.
No production installation or new provider call is claimed by this report yet.

No source truncation or hidden summarization is added. Native compaction occurs
before inlet; the full File source is restored independently of the compacted
conversation. The installed framework has no universal model-window getter or
exact tokenizer: native compaction estimates tokens and its threshold is not a
provider window. An oversized source must receive an explicit provider/native
error; universal fit in every model is not claimed. Real provider-limit and
model-compliance acceptance remains a separate boundary from the offline tests.

Raw customer text, private snapshots and runtime receipts remain in ignored
local evidence or the private task directory on the server. Public source
contains only synthetic test material and sanitized evidence descriptions.
