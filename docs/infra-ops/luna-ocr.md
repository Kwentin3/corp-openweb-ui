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

Current step: implementation and independent component checks prepared. Three
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
output tokens). No implementation installed or Documents settings changed yet.

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
An absent/deleted/inactive Function fails closed. The module is removable and
the previous default loader is the recorded baseline. No live rollback test or
ordinary-user acceptance is claimed before the receipts below are recorded.

## Constraints and unresolved risks

- Existing main checkout and unrelated worktrees remain untouched.
- Never run a clean image build on the production VPS. Any bounded runtime
  diagnostic needs explicit resource/stop/retention ownership.
- Whole-document generation can omit source content despite valid JSON; review
  original pages and omissions, not just page/token counts.
- Confirm native connection auth type and model catalog availability on startup.
- No hidden retries, fallback model, duplicate OCR storage or original-byte
  replacement. Reprocessing must remain an explicit native operation.
- Event installation/configuration and production activation must be reviewable
  and reversible; retain the previous native extraction settings.

References:
- https://docs.openwebui.com/features/extensibility/plugin/functions/event/
- https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/external/
- https://developers.openai.com/api/docs/models/gpt-6-luna
