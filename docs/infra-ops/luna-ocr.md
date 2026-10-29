# Native PDF OCR with GPT-6 Luna

## GOAL and acceptance

Implement PDF OCR through `gpt-6-luna` in the existing OpenWebUI file intake,
without modifying upstream core. Preserve original bytes and File ID, native
provider connections and authorization, native File content/status and RAG.
Later questions, reload and model changes must reuse the stored text.
Unreadable/failed/incomplete extraction must not look successful.

Acceptance requires ordinary-user upload of the complete 22-page source,
source-to-text review including numbers, negations, numbered clauses and table
cells, inspection of actual OCR/model input and output, retained original hash,
cache reuse and error behavior, and recorded time/token cost. Green unit tests
alone are insufficient. Private source/chat/provider artifacts stay outside Git.

## Current verified state

- Base: `7c759316cd50656071c09bffd7f7c2fe5d9751f9`, branch
  `agent/luna-ocr`, isolated worktree `D:/Users/Roman/Desktop/corp-openweb-ui-luna-ocr`.
- Portal API reports 0.12.2; deployed image
  `sha256:a0f5752afafd24ae065190ef28d88717e9a29c739ccb23be1e2d3e7ff7bfe424`.
- `gpt-6-luna` is now visible with vision enabled; 5.6 Luna was disabled by user.
- The existing 22-page image PDF produced 22 empty native documents joined into
  21 spaces. File processing failed before model invocation; the model's native
  file-reading tool also returned those spaces.
- Effective extraction engine is empty/default, PDF image OCR is off. The
  unused uppercase `rag.CONTENT_EXTRACTION_ENGINE` key is not the native setting.

## Selected native seam, pending qualification

Official Event Functions can register FastAPI endpoints on startup. Official
External Document Extraction calls a raw-byte PUT `/process` and consumes
`page_content`/`metadata` documents. Combine those existing seams in one Event
Function inside OpenWebUI: no sidecar or second provider client/key.

Boundary map:

| Meaning | Existing owner / public contract | Consumer |
| --- | --- | --- |
| Original identity, bytes, access | native Files / Storage / access checks | extraction endpoint |
| Extraction selection and integration credential | native Documents Config | native external loader and endpoint |
| Route lifetime | native Event Function startup/enable/disable | FastAPI app |
| OCR instructions and PDF-to-text representation | small extraction adapter | native provider invocation |
| Model route, credentials and ACL | native `routers.openai.responses` (Responses) or `utils.chat.generate_chat_completion` (Chat Completions) | configured `gpt-6-luna` |
| File content, status, indexing and reuse | native `process_file` | normal chat/RAG/tools |
| Non-PDF parsing | existing native loader with request-local default config | same native ingestion |

The adapter authenticates the native loader, binds request bytes to native
storage and requester access, invokes the existing model owner with a fresh
request state and explicit OCR messages, validates page coverage and returns
native documents. No chat history, tool loop, RAG or auxiliary chat tasks run
inside OCR. It must not globally toggle extraction settings while handling a
request. Preserve non-PDF/media handling; selecting External otherwise expands
image/video admission and intercepts all document types.

## Work slices and current next step

1. Verify installed lifecycle, loader and provider contracts; rehearse final
   request/schema offline on the real source and qualify a bounded page sample.
2. Implement the smallest Event adapter and behavior checks for byte/access
   binding, complete/error output, non-PDF delegation and lifecycle.
3. Qualify full-source extraction and native cache reuse, run necessary CI,
   prepare a reversible activation and verify ordinary-user portal behavior.

Current step: installed, ordinary-user acceptance passed and the original failed
attachment reprocessed; closing source delivery and independent review. Three
source pages (1, 6, 22) completed through the native provider connection in
26.872 seconds: 9,313 input and 2,808 output tokens, estimated $0.0023353 at
the published standard tariff. Original clause 2.3 negations and clause 2.7
limits matched the source; page 22 identifiers matched the image. The seal's
small illegible text was explicitly flagged. This is a bounded provider probe,
not ordinary-user ingestion acceptance. The full-source raw Responses probe
completed in 145.755 seconds with 66,028 input / 19,076 output tokens and 69,214
text characters across all 22 pages (estimated $0.0161408). Source comparison
found a malformed merged table header. The prompt was minimally refined; a
bounded page-18 repeat produced all eight leaf columns with consistent rows,
all visible header text and empty cells (19.011 seconds, 3,387 input / 1,767
output tokens). The qualified source was subsequently installed and the five
Documents settings below activated through native administration APIs.

The installed Chat Completions conversion drops raw Responses completion
status. The adapter therefore uses the existing native Responses endpoint for
a Responses connection and checks its raw status/output. It preserves native
model ACL, connection and transport ownership and sets `store=false`.

## Installation and rollback

Install the exact source as native Event Function `luna_pdf_ocr`, enable it and
verify its unauthenticated PUT route returns 401 before selecting the loader.
No image build, container restart, package install or upstream edit is needed.
The installed runtime already provides FastAPI, Pydantic and pypdf.

Retain a private backup of only the five affected native Documents settings.
Set them through `/api/v1/retrieval/config/update`:

| Native setting | Value |
| --- | --- |
| `CONTENT_EXTRACTION_ENGINE` | `external` |
| `EXTERNAL_DOCUMENT_LOADER_URL` | `http://127.0.0.1:8080/api/v1/luna-pdf-ocr` |
| `EXTERNAL_DOCUMENT_LOADER_API_KEY` | generated integration credential; native Config only |
| `EXTERNAL_DOCUMENT_LOADER_HEADERS` | `{"X-OCR-File-Id":"{{FILE_ID}}","X-OCR-User-Id":"{{USER_ID}}"}` |
| `CONTENT_EXTRACTION_SUPPORTED_MEDIA_MIME_TYPES` | `[]` (preserves existing media route) |

Defaults: 20 MiB, 50 pages, one active request per process, 300 seconds, 64,000
output tokens, no retries/fallback. Auth, native file ACL and original stored
byte hash are checked before any model call. Timed-out local parser workers
retain their admission slot until finished. Native processing owns file error
status. Page uncertainty remains visible in saved text as a labelled note.

Rollback: restore the previous extraction engine first, then the other four
settings, then disable the Function. Do not delete native cached file content.
The config-update API skips JSON null values. The previous supported-media
setting was null; restore that exact value through native
`await Config.upsert({'rag.content_extraction.supported_media_mime_types': None})`
in the installed application environment when performing a full rollback.
An absent/deleted/inactive Function fails closed. The module is removable and
the previous default loader is the recorded baseline. Live rollback was not
exercised; registration, enable/disable and failure behavior have component
coverage. The installed route was verified before changing the loader.

## Acceptance receipts, 2026-10-29

- Installed Event content SHA256:
  `5cf11c86f9baecb74a8d17f1188fae7e39bfc938aca9f33bcac1daec5cf162c4`.
  Readback matched the candidate in source commit `c43a38a5`; the installed
  upstream image stayed unchanged and healthy, restart count zero.
- A fresh native account with role `user` uploaded the complete source using
  the normal chat file chooser. The adapter returned 22 page documents; native
  ingestion stored 69,111 characters and 96 indexed chunks, status completed.
  Original stored bytes were independently hash-checked, not merely trusted
  from client metadata: 13,440,229 bytes, SHA256
  `a7b379fc2fece3c4edde6c31d809583f7af6125c1384ee5b42be6c20ee2cb844`.
  The upload's File ID remained the same throughout extraction and later use.
- OCR took 146.243 seconds, with 66,072 input and 19,071 output tokens.
  Estimated standard model cost: $0.0161427, excluding embedding and later chat
  calls or any gateway markup. Native indexing finished about 16 seconds later.
- Final request construction and the installed native Responses form/converter
  were replayed: complete PDF bytes, explicit OCR instructions and strict page
  schema survived; no parent chat, tools or previous response ID were included.
  Raw Responses completion status was checked before returning documents.
  A separate complete provider HTTP trace of the nested production call was
  not captured; actual file bytes, pinned request builder and native boundary
  replay establish the input, while provider usage and native output establish
  the completed call.
- GPT-6.1 Sol answered from native RAG chunks and called `view_knowledge_file`
  on the same File ID; its saved tool result contained 20,000 characters.
  It quoted clause 2.3 with both critical negations and correctly answered the
  one-contract / twenty-card limits. After a browser reload and model change,
  GPT-6 Luna answered twenty cards and three working days from native sources.
  File text SHA256 remained
  `3e7ab36e0f65c796bcab399f5514625567ee88b7d206795fa0e045b40515b490`.
  Bounded native logs across upload, both answers and reload show exactly one
  OCR completion for that acceptance upload.
- The acceptance upload's table preserved all eight leaf columns and empty cells. A full
  comparison with the related DOCX and targeted PDF image review covered pages
  6, 9, 11, 12, 18, 21 and 22: important amounts, deadlines, numbered clauses,
  negations and numeric identifiers agreed. None of the DOCX's sixty standalone
  Russian negations disappeared. This is source qualification, not a claim of
  character-perfect transcription of every image.
- One known literal error remains: a URL on page 9 ends with a Cyrillic `т`
  instead of Latin `t`. The stored text explicitly flags that URL in
  `[OCR uncertainty, page 9]`. Seal uncertainty is also visible to later models.
  Do not silently normalize uncertain source characters or claim 100% OCR
  accuracy. Page-count/JSON success alone was not used as quality acceptance.
- DOCX through the new route exactly matched its prior native extraction:
  68,080 characters. A text file also retained its exact content. An invalid
  PDF failed before any OCR call, stored no content and showed the normal UI
  error toast: `PDF is invalid or encrypted`.
- 52 component/ASGI checks passed locally and in the Native Luna OCR CI job;
  Active CI passed for the candidate. Native owner fakes in portable tests are
  distinguished from the installed-source replay and real user evidence.
- The temporary account, chat and all five acceptance files were deleted via
  native APIs after private receipts were retained. File inventory readback
  was zero, deleted chat readback 401 and deleted user readback 404. Original
  customer attachments and chat history were retained.

Detailed private inputs, provider probes, source images, file/chat readbacks,
cache-window logs, runtime identity and cleanup receipts remain in the original
checkout's ignored `local/pdf-audit-20261029/` directory. They are intentionally
excluded from Git. No server follower or diagnostic service was started.

The original failed PDF was explicitly reprocessed once through native
`/api/v1/retrieval/process/file` under its existing File ID. It now has status
completed, error null and 69,236 stored characters instead of 21 spaces; its
original-byte hash is unchanged. Native OCR took 157.648 seconds, 66,073 input /
18,869 output tokens (estimated $0.0160418), and processing including indexing
completed in 186.431 seconds. Text SHA256 is
`7de523196a52c90a6cb7449a59a51efa910b79243ae2618a31c0c05f52aa6cfa`.
The previously ambiguous URL was transcribed with the correct Latin `t` in this
run. The merged table header was linearized with inconsistent Markdown column
counts, while its visible header text was retained and page-18 uncertainty
explicitly recorded. Table layout is consequently a known qualification limit,
not a guarantee of character/geometry-perfect reconstruction. Important clauses
2.3/2.7 and all sixty standalone source negations were retained. Customer chat
messages were not edited; existing tools/RAG can now read the original File ID.

## Constraints and unresolved risks

- Existing main checkout and unrelated worktrees remain untouched.
- Never run a clean image build on the production VPS. Any bounded runtime
  diagnostic needs explicit resource/stop/retention ownership.
- Whole-document generation can omit source content despite valid JSON; review
  original pages and omissions, not just page/token counts.
- Current static-bearer Responses connection was verified. Session-auth routes,
  model aliases/parameter overrides and non-vision models fail closed.
- No hidden retries, fallback model, duplicate OCR storage or original-byte
  replacement. Reprocessing must remain an explicit native operation.
- Event installation/configuration and production activation must be reviewable
  and reversible; retain the previous native extraction settings.

References:
- https://docs.openwebui.com/features/extensibility/plugin/functions/event/
- https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/external/
- https://developers.openai.com/api/docs/models/gpt-6-luna
