# Draft reply: supported preparation of uploaded media before Send

Prepared 2026-10-07 for an upstream **Discussion**, not an unsolicited code PR.
No upstream publication or maintainer agreement is claimed.

Related discussion already exists:
[#24239](https://github.com/open-webui/open-webui/discussions/24239). Maintainers
declined a general pre-storage hook and recommend external content extraction
plus file deletion, inviting a concrete case that this cannot serve. Do not
open a duplicate proposal or assume that invitation requests an implementation.
The text below is material for a focused reply about media attachment replacement.

## Workflow and question

An ordinary user attaches an MP4 or M4A file. An isolated media service prepares
an MP3, without provider transcription at upload time. OpenWebUI should retain
the native File ID, ownership and chat attachment, show the final filename/size,
and wait for preparation before sending the draft. Transcription starts on Send;
the selected chat model receives text. Failed preparation must remain visible.

Is there a supported extension contract for claiming an uploaded File **before**
default processing, completing or failing that processing asynchronously, and
refreshing the attachment from the authoritative native File metadata?

The desired boundary leaves authorization, storage, chat attachments and the
draft queue with OpenWebUI. Conversion and transcription stay in the extension
and its existing service. We do not need a second file registry, chat route or
agent loop. The exact hook name and implementation should belong to upstream.

## What we checked

- Stable v0.11.4, upstream commit
  `8bd8b4fac5e059578ac0c74b3c18d11139f88b7d`.
- Read-only inspection of the four affected files at upstream `dev`
  `56b6b660a8c22e51359070732c3d65dfc15fe01d`. This is source inspection, not a
  live acceptance test of `dev` and not a claim that every possible seam was ruled out.
- [Event Functions](https://docs.openwebui.com/features/extensibility/plugin/functions/event/)
  notify after activity; documented callbacks cannot block or rewrite the
  in-band upload. A Filter runs on Send, too late to own upload preparation.
- v0.11.4 already provides the draft's wait-for-processing behavior. We reuse it.
- The existing external document loader returns `page_content` and document
  metadata for text extraction/indexing. Supported STT MIME types are handled
  before that loader; other videos are stored as completed unless explicitly
  enabled for extraction. This is source evidence, not a live rejection of every
  possible external-loader integration.

Our case does not require rejecting bytes before storage, and is not an AV/DLP
proposal. It needs a usable audio attachment with the original native File ID
and refreshed filename/size. Returning extracted text, or deleting the File,
does not establish that result. A callback that replaces native File bytes and
metadata and keeps processing pending until completion still needs an explicit
supported contract and browser verification. We welcome a simpler native route.

## Two separable gaps

1. **Extension handoff and attachment metadata.** Our current narrow, version-pinned
   exception adds a pre-processing handoff and fetches the final native File
   metadata after processing. The frontend preserves native processing errors.
   Business-specific state must not enter a generic upstream contract.
2. **Bounded local uploads.** The inspected native `LocalStorageProvider.upload_file`
   reads the entire upload before writing. Our local exception writes and hashes
   bounded chunks. This independent storage concern could be addressed separately;
   other storage providers and multiple replicas have not been qualified by us.

The existing local reference is
[the reviewed four-file patch](https://github.com/Kwentin3/corp-openweb-ui/blob/main/deploy/openwebui-patches/media-upload-v0.11.4/proposed.patch).
It contains a project-specific state check and is **not** an upstream-ready diff.
Our Event Function uses internal File/Storage APIs, so a supported replacement
would reduce upgrade coupling. No core conversion/provider logic is proposed.

## Evidence and limits

The customized v0.11.4 installation has been qualified with normal-user MP4/M4A
upload, preparation before Send, same-ID MP3 attachments, cached transcripts,
processing failures, recovery and cleanup. These results concern our pinned
exception, not the unmodified stable or `dev` build. No private user data,
credentials or original transcripts belong in the public proposal.

This Discussion asks whether a native solution exists or is planned, and which
boundary maintainers prefer. We will follow the
[contribution policy](https://docs.openwebui.com/contributing/#submit-code):
no code or test PR without an explicit maintainer request. If upstream supplies
an equivalent supported path, we will qualify it and remove our exception.
