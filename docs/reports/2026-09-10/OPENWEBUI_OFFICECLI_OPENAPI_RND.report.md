# OpenWebUI OfficeCLI OpenAPI R&D

Date: 2026-09-10

Goal: [Issue #451](https://github.com/Kwentin3/corp-openweb-ui/issues/451)

Repository base: `815d23c12fadb7f5938013dc85e5a6f322494cd2` (`origin/main`)

Route: `agent/issue-451-officecli-openapi-rd`

Scope: R&D only; OpenAPI only; no production activation

## 1. Verdict

OfficeCLI is suitable as the external Office engine, but it does not provide a
production OpenAPI server. The KISS architecture is one small global OpenAPI
Tool Server adapter that:

1. receives the native OpenWebUI opaque file ID and the unchanged official
   OfficeCLI command payload;
2. uses the caller session forwarded by OpenWebUI to read the source through
   the native OpenWebUI Files API;
3. runs a release-pinned OfficeCLI binary in an ephemeral request workspace;
4. uploads the result through the native OpenWebUI Files API as the same user;
5. attaches the returned native file object to the chat message through the
   native OpenWebUI event endpoint.

The adapter owns HTTP translation and call order only. It has no database, ACL,
file registry, durable document store, sharing rules, Office object model, or
Broker Reports dependency.

```text
OpenWebUI chat + native tool calling
        |
        | global OpenAPI tool, native OpenWebUI access control
        v
thin OfficeCLI OpenAPI adapter
        |
        | exact OfficeCLI command vocabulary
        v
release-pinned OfficeCLI binary
        |
        | generated DOCX/XLSX/PPTX bytes
        v
OpenWebUI Files API + message files event
```

## 2. Goal skeleton compliance

| Invariant | Result |
| --- | --- |
| OpenAPI only | Kept. No MCP or Open Terminal route is proposed. |
| OpenWebUI owns users, groups, permissions, files, sharing, and attachments | Kept through native authenticated APIs and native Tool Server access control. |
| OfficeCLI owns Office operations | Kept by passing official OfficeCLI commands without a second Office vocabulary. |
| No OpenWebUI core fork | Kept. The route uses the pinned version's existing Global Tool Server, Files API, and event API. |
| No duplicate storage or registry | Kept. Only request-scoped temporary files exist inside the adapter. |
| No large implementation before architecture proof | Kept. This deliverable defines one bounded proof and contains no runtime implementation. |

## 3. Established owners and contracts

| Meaning | Existing owner | Boundary contract | Consumer |
| --- | --- | --- | --- |
| Chat, model context, tool enablement | OpenWebUI | native chat and Global Tool Server configuration | selected model |
| User/group access and sharing | OpenWebUI | native connection and file access checks | OpenAPI call and Files API |
| Source and result file custody | OpenWebUI Files/Storage | opaque file ID, authenticated native file API, native file object | adapter and chat message |
| DOCX/XLSX/PPTX semantics | OfficeCLI | official CLI commands and JSON envelopes | adapter |
| HTTP translation and call order | new thin adapter | OpenAPI request/response | OpenWebUI Tool Server |
| Durable result presentation | OpenWebUI | `files` message event | user |

The repository already requires OpenWebUI-native extensions before a fork and
places Tools/OpenAPI Tool Servers ahead of private sidecars
([extension-first pattern](../../stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)).
The pinned deployment is `ghcr.io/open-webui/open-webui:v0.9.6`
([compose pin](../../../compose/openwebui.compose.yml)).

## 4. OpenWebUI evidence

### 4.1 Current recommendation

Current official OpenWebUI documentation treats OpenAPI Tool Servers as the
standard external HTTP capability surface. A Global Tool Server is configured
by an admin, invoked from the OpenWebUI backend, shared through OpenWebUI's own
access controls, and enabled in chat by the user:

- [OpenAPI Tool Servers](https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/)
- [OpenWebUI integration](https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/open-webui/)

Native function calling is the supported agentic route. On pinned `v0.9.6` it
must be explicitly selected; `v0.10.0` made it the default. Tool reliability
still depends on the selected model producing valid structured calls.

### 4.2 Exact pinned `v0.9.6` seam

The repository pin resolves to upstream OpenWebUI commit
[`1a97751e`](https://github.com/open-webui/open-webui/commit/1a97751e376e00a1897bc3679215ae1c7bd8fd42).
At that exact tag:

- Global OpenAPI server tools are resolved server-side, checked through the
  existing connection access owner, and executed as HTTP operations identified
  by `operationId`
  ([tool resolution](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/utils/tools.py#L321-L410),
  [HTTP execution](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/utils/tools.py#L1377-L1529)).
- `auth_type=session` forwards the authenticated request bearer to the tool
  server; the official UI describes this as forwarding the system user session
  credentials
  ([header construction](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/utils/tools.py#L104-L163),
  [connection UI](https://github.com/open-webui/open-webui/blob/v0.9.6/src/lib/components/AddToolServerModal.svelte#L682-L722)).
- Native function calling adds stored user-message attachment references to
  model context as `<attached_files><file ... url="<opaque file ID>"/></attached_files>`;
  despite the attribute name, `url` contains the uploaded file ID, not a ready
  download URL
  ([composer file shape](https://github.com/open-webui/open-webui/blob/v0.9.6/src/lib/components/chat/MessageInput.svelte#L645-L668),
  [attachment context](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/utils/middleware.py#L1704-L1753)).
- File download is authorized by the existing OpenWebUI owner/share access
  check, not by adapter logic
  ([file content route](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/files.py#L651-L691)).
- File upload creates the native File row through the existing Files/Storage
  owner. `process=false` avoids an unrelated RAG processing path
  ([upload route](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/files.py#L218-L354)).
- The authenticated chat event route targets an existing chat/message, and a
  `files` event persists native file objects on the message
  ([event route](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/chats.py#L1067-L1109),
  [files persistence](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/socket/main.py#L894-L987)).

This exact-source evidence is sufficient to select the seam. It is not a live
runtime qualification: deployment configuration, the built image, and browser
behavior still require the bounded proof in section 9.

### 4.3 Native file lifecycle

The chosen file flow deliberately calls OpenWebUI back through its public,
authenticated routes:

```text
model receives native opaque attachment ID
-> OpenAPI call carries file_id
-> adapter reuses forwarded caller bearer
-> GET /api/v1/files/{file_id}/content from OpenWebUI
-> OfficeCLI works on an ephemeral local copy
-> POST /api/v1/files/?process=false as the same caller
-> OpenWebUI returns its native file object
-> POST /api/v1/chats/{chat_id}/messages/{message_id}/event type=files
-> OpenWebUI persists and renders the attachment
```

No private OpenWebUI filesystem path, database model, or Storage implementation
crosses the service boundary.

## 5. OfficeCLI evidence

The reproducible R&D baseline is OfficeCLI
[`v1.0.148`](https://github.com/iOfficeAI/OfficeCLI/releases/tag/v1.0.148),
published 2026-09-07 and resolving to commit
[`0a450e4`](https://github.com/iOfficeAI/OfficeCLI/commit/0a450e43389531eadf05510dff209d541c1dec1e).

### 5.1 No production OpenAPI server

The release tree has no OpenAPI/Swagger specification or standalone authenticated
HTTP service. `officecli watch <file>` does contain local preview endpoints, but
they are document-scoped, loopback-only, unauthenticated, tied to preview/SSE
lifecycle, and do not expose the full OfficeCLI lifecycle. It is not the
integration boundary:

- [watch HTTP API](https://github.com/iOfficeAI/OfficeCLI/wiki/command-watch#http-api)
- [WatchServer source](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.148/src/officecli/Core/Watch/WatchServer.cs)

### 5.2 Official interface to reuse

The complete interface is the CLI. It supports deterministic JSON envelopes,
structured errors, `view`, `query`, `create`, atomic `batch`, `validate`, and
HTML/screenshot rendering. The official Python and Node SDKs are intentionally
thin resident-pipe clients that retain the same batch vocabulary:

- [OfficeCLI README](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.148/README.md)
- [Python SDK](https://github.com/iOfficeAI/OfficeCLI/tree/v1.0.148/sdk/python)
- [Node SDK](https://github.com/iOfficeAI/OfficeCLI/tree/v1.0.148/sdk/node)
- [batch contract](https://github.com/iOfficeAI/OfficeCLI/wiki/command-batch)

The first proof should use direct one-shot subprocess calls, not the resident
SDKs. `view` and other ordinary commands can auto-start a resident, so the
adapter must set the exact release guard described in section 5.3. This keeps
the intended process and file lifetime equal to one HTTP request. `batch`
opens the file once, applies the official command array atomically, and saves
before returning.

The adapter must evaluate both process exit status and the OfficeCLI JSON
`success` field. Large JSON output can use OfficeCLI's official `outputFile`
spill contract, which the adapter must unfold before returning its HTTP JSON.

### 5.3 Reproducible runtime

The service image should install the exact release asset, verify its published
SHA-256, and set its supported one-shot guards:

```text
OFFICECLI_SKIP_UPDATE=1
OFFICECLI_NO_AUTO_RESIDENT=1
```

`OFFICECLI_NO_AUTO_RESIDENT=1` disables the automatic resident start used even
by `view`; it does not prevent a command from connecting to a resident that
already exists for the same path
([TryResident](https://github.com/iOfficeAI/OfficeCLI/blob/0a450e43389531eadf05510dff209d541c1dec1e/src/officecli/CommandBuilder.cs#L578-L605),
[view route](https://github.com/iOfficeAI/OfficeCLI/blob/0a450e43389531eadf05510dff209d541c1dec1e/src/officecli/CommandBuilder.View.cs#L116-L138)).
The adapter therefore creates one unique request workspace and unique output
path before any OfficeCLI call, never invokes `open`, and records that no
resident was started before returning the uploaded result. It does not need a
process manager. `OFFICECLI_SKIP_UPDATE=1` prevents version drift. OfficeCLI
is Apache-2.0 licensed and publishes self-contained
Linux/Alpine/Windows/macOS release binaries. PNG screenshot rendering has
additional browser dependencies; it is not required for the first structural
DOCX edit proof.

## 6. Minimal OpenAPI contract

The first proof uses two document operations and two read-only official
guidance operations. The guidance is served from the installed, release-pinned
OfficeCLI binary through the same OpenAPI Tool Server; it is not copied into a
second Word instruction set and gives no installation or desktop authority.

### `load_officecli_skill`

```json
{"skill": "word"}
```

For this DOCX proof, `skill` is the single allowed value `word`. The adapter
runs the official `officecli load_skill word` and returns its exact output as a
tool result. It does not expose arbitrary skill installation, plugins, or
filesystem locations.

### `get_officecli_help`

```json
{"topic": ["docx", "set", "paragraph"]}
```

The adapter validates the small token array and runs `officecli help` with
those tokens. For the proof, accepted topics are limited to the chosen DOCX
operation and its target element. The model calls this operation whenever a
property name, value format, or syntax is uncertain, as required by the
[official SKILL.md](https://github.com/iOfficeAI/OfficeCLI/blob/0a450e43389531eadf05510dff209d541c1dec1e/SKILL.md).
No hand-written Office property knowledge is added to prompts or adapter code.

The two document-operation payloads preserve OfficeCLI's own vocabulary rather
than inventing one:

### `inspect_office_document`

```json
{
  "file_id": "<opaque OpenWebUI file ID>",
  "command_payload": {"command": "view", "mode": "annotated"}
}
```

Returns the OfficeCLI JSON/text result needed to address the requested element.
`query` may be passed as the official command when required; the adapter does
not interpret document meaning.

### `apply_office_batch`

```json
{
  "file_id": "<opaque OpenWebUI file ID>",
  "output_name": "document-updated.docx",
  "commands": [
    {"command": "set", "path": "/body/p[1]", "props": {"text": "..."}}
  ]
}
```

The adapter first copies the authenticated OpenWebUI download to the new
`output_name`, because OfficeCLI batch mutates its target file in place. It then
runs the official atomic batch on that output copy, runs OfficeCLI validation,
and returns the OpenWebUI-native uploaded file object together with its
`result_file_id`. Validation is OfficeCLI behavior; the adapter only orders the
calls and reports the result. Atomic batch protects the output copy from partial
application; the prior copy step is what keeps the OpenWebUI source bytes
unchanged.

### `create_office_document`

```json
{
  "format": "docx",
  "output_name": "new-document.docx",
  "commands": [
    {"command": "add", "parent": "/body", "type": "paragraph", "props": {"text": "..."}}
  ]
}
```

This maps to `officecli create`, the official atomic batch, and validation. It
is part of the eventual product surface but is not part of the minimal edit
proof; it is deferred until that proof is qualified.

There is no format-specific REST object model, generic job framework, durable
adapter state, or adapter-side sharing policy.

## 7. Why existing project services must not be reused

Broker Reports and NDFL are a separate domain and a parallel active work lane.
Their code is not an OfficeCLI integration foundation:

- the Broker `OpenWebUIFileBytesResolver` imports private OpenWebUI models and
  Storage directly and applies an owner-equality rule; using it would bypass the
  public boundary and narrow native sharing
  ([resolver](../../../services/broker-reports-gate1-proof/broker_reports_gate1/openwebui_file_bytes.py));
- Broker/NDFL artifact publication is domain-specific and in-process;
- the STT service is a useful FastAPI packaging precedent, not a shared Office
  service or contract owner.

Any proof implementation belongs under a new
`services/officecli-openapi-proof/` root. It must not modify
`services/broker-reports-gate1-proof/**`, the STT service, or OpenWebUI core.

## 8. Confirmed limits and open runtime questions

1. **Attachment discovery is native-mode-specific.** Exact `v0.9.6` source
   injects opaque attachment IDs for stored user messages. The selected deployment
   and model must prove that Native is selected, built-in tool processing is
   active, and the model supplies the correct ID to the tool.
2. **Session forwarding must be qualified live.** Exact source supports
   `auth_type=session`; current general event documentation often describes the
   default configuration where user credentials are not forwarded. The proof
   must verify the configured global connection rather than infer from docs.
3. **Chat/message routing needs native identifiers.** Use per-connection custom
   headers with `{{CHAT_ID}}` and `{{MESSAGE_ID}}`, or the exact supported
   forwarding setting. Do not create an adapter chat registry.
4. **Office binary responses are not automatically Office attachments.** The
   adapter must upload through OpenWebUI and emit the returned native file object;
   returning DOCX bytes directly from an OpenAPI operation is insufficient.
5. **Continuation is a native-result hypothesis, not a reattachment fallback.**
   The adapter returns the new native `result_file_id` in its tool result and
   emits the matching native file event. The proof must establish whether that
   ID remains available to the model through ordinary OpenWebUI tool-result
   history on the next user turn. Manual download, reupload, or reattachment is
   not a successful continuation and must be recorded as a product gap; no
   adapter-side document/revision registry is authorized.
6. **Structural validity is not preservation evidence.** `validate` checks
   OpenXML validity, not that the requested edit left unrelated Word content
   and formatting intact. The proof therefore needs the focused before/after
   checks in section 9, not a new test framework.
7. **No production claim.** Static source evidence does not prove deployed image,
   model behavior, file access, browser persistence, real Office fidelity, or
   process cleanup.

## 9. One minimal next proof

This R&D terminates with one implementation-ready, bounded proof definition.
It does not itself execute or activate the proof.

### Proof scope

One privacy-safe DOCX made in ordinary Word, with a visible section `3.2`, a
table, header/footer, and mixed text formatting; one ordinary corporate user;
one fresh chat; one pinned OfficeCLI `v1.0.148` binary/version with a bounded
subprocess per operation. The model receives the official `word` skill and
uses official help when needed. The document path has two guidance reads
(`load_officecli_skill`, `get_officecli_help`) and two document operations:
`inspect_office_document` and `apply_office_batch`.

### Proof steps

1. Build an isolated `services/officecli-openapi-proof/` service with no DB and
   no imports from Broker, NDFL, STT, or OpenWebUI internals.
2. Install and checksum the pinned OfficeCLI binary. Set
   `OFFICECLI_SKIP_UPDATE=1` and `OFFICECLI_NO_AUTO_RESIDENT=1`; use a unique
   request workspace/output path, never invoke `open`, and prove from the
   request receipt that no resident was auto-started and all child work ended
   before the result is uploaded.
3. Register it as a Global OpenAPI Tool Server through the native admin surface,
   with native access control, `auth_type=session`, and chat/message header
   templates.
4. In the real Web UI, upload the DOCX through the ordinary file control. Let
   the selected model obtain `load_officecli_skill word` and, when the requested
   edit needs syntax/property confirmation, `get_officecli_help`; it must not
   guess Word properties.
5. Ask the model to change section `3.2`.
6. Prove from browser network evidence and adapter/OpenWebUI receipts that:
   - the model received and passed the native opaque attachment ID;
   - official skill/help output, when used, came from the pinned binary;
   - OpenWebUI authorized the source GET under its existing sharing model;
   - `view annotated` identified the target;
   - one atomic OfficeCLI batch produced the edit;
   - the source file remained unchanged;
   - the result was uploaded by the native Files API;
   - the native file object and its `result_file_id` were persisted on the
     assistant message and returned through the tool result;
   - the ordinary user downloaded and opened the result;
   - section `3.2` changed, while fixed unaffected checks of ordinary Word text,
     table content, header/footer, and selected mixed formatting match the
     before-state; and
   - Word opens both source and result for the same focused before/after check.
   This is an addressable checklist, not a new validation, rendering, or
   document-diff subsystem.
7. In the next turn, ask the ordinary user-path question "now change this too"
   without downloading, reuploading, or reattaching the generated file. Prove
   that the model receives the prior `result_file_id` from native tool-result
   history, supplies it to the next document operation, and returns a further
   native result attachment.
8. Remove only proof-created runtime state and confirm Broker/NDFL files and
   services were unchanged.

### Proof acceptance terminal

```text
OFFICECLI OPENAPI DOCX EDIT PROOF QUALIFIED
```

If any native file, session, attachment, source-preservation, process-lifetime,
or continuation seam fails, stop with:

```text
OFFICECLI OPENAPI PROOF BLOCKED / EXACT NATIVE GAP RECORDED
```

In particular, a first edit that requires manual file reattachment for the
second edit is not `QUALIFIED`; record the native continuation gap and stop.

Do not add a second storage, ACL, browser patch, Action, MCP route, or OpenWebUI
core change to make a failing proof appear green.

## 10. R&D terminal

```text
R&D CLOSED / ONE NARROW CHAT PROOF READY
```

The architecture is selected, ownership is explicit, the adapter gap is
confirmed, and one bounded proof is specified. No runtime implementation,
deployment, provider call, production mutation, or activation was performed
by this R&D slice.
