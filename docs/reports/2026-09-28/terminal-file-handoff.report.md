# Native Terminal file handoff candidate

Status: private end-to-end qualification passed; no shared deployment.

## Shared-route candidate

The global Office Filter now has a narrowly scoped activation contract for the
handoff components. A request on an explicitly qualified direct model receives
the transfer Tool, full artifact-workflow Skill and default system Terminal only
when it carries an OOXML Office input (`docx`, `xlsx`, `pptx` and macro-enabled
variants). An explicitly selected Terminal is preserved. Requests without an
Office input, auxiliary tasks, caller-supplied tool schemas and unqualified
models do not receive Terminal capabilities. Empty valves disable each binding
independently without disabling the existing OfficeCLI route.

The deployed instance currently has 23 accounts and closed signup. No
`LICENSE_KEY` is configured. Official Open Terminal guidance permits the free
built-in multi-user mode only for a small group whose users trust each other at
the same level: homes are separate, while the kernel, processes, network and
resource pool are shared. The production alternative is per-user containers via
the Enterprise Terminals Orchestrator. Shared activation therefore waits for an
explicit isolation choice; the single-user QA container is not being relabelled
as a multi-user service.

Official release identities checked on 2026-09-28: Open Terminal `v0.14.0`
(`ghcr.io/open-webui/open-terminal@sha256:81a5394b3cd4ae32adb600f2135f09ee124de37f26b0a780e2f5692472c0fc5c`)
and Terminals `v0.2.4` (linux/amd64 manifest
`sha256:e0d03626d75ac8232ab582b9f047715dd25d2eb4da9d743c28b9f1377499c5c4`).
The full Open Terminal image contains LibreOffice, openpyxl 3.1.5,
python-docx 1.2.0 and python-pptx 1.0.2. An isolated server probe of its free
multi-user mode created distinct homes for two synthetic users and denied a
cross-home file read with HTTP 403. It also confirmed the documented security
boundary: the container requires a writable root and retains its default
capabilities for dynamic account provisioning; the users still share one
container. The probe had no network and was removed after the check.

## Need and native alternatives

The full Excel pilot completed via native Open Terminal on Linux, but its sources
were loaded separately in the file manager and the operator archived its result
as a normal Files attachment. An agent working from existing chat attachments
still needs an authorized byte-transfer path, without passing credentials or
file contents through model context.

Deployed OpenWebUI 0.9.6 has native Files APIs, a permission-checked Terminal proxy,
selected `terminal_id` in the native request, and native attachment events. It lacks
the newer chat-input Filesystem upload branch. Stable upstream
[0.11.4](https://github.com/open-webui/open-webui/releases/tag/v0.11.4) includes that
branch in `MessageInput.svelte`. Upgrading this deployment also affects pinned
STT, Broker Reports and Google protocol overlays, so it is not an isolated Office
configuration change. No production upgrade is authorized or performed by this
candidate. Native Filesystem delivery is also distinct from a Files-store artifact.

## Ownership and contracts

- File identity, access and bytes → OpenWebUI Files → authenticated file metadata/content/upload APIs → transfer Tool.
- Selected environment and access → native tool metadata and Terminal registry/proxy → selected `terminal_id`, allowed-server list, file endpoints → transfer Tool.
- Document processing → agent and installed tools/libraries → completed output path → transfer Tool.
- Durable publication and attachment → OpenWebUI Files and chat events → native File plus `files`/`chat:message:files` events → chat UI.

The new Tool is a **call-order coordinator**, with representation adaptation for
the native attachment event. It performs no Office parsing, grouping, calculation,
planning, model calls or shell execution. It owns no server credentials, file
registry or alternate storage. Its only staging is a bounded temporary byte stream;
the native owners authorize and persist both ends. The user's bearer token is sent
only to this OpenWebUI instance, never to Terminal or the model.

`stage_chat_file` requires an explicit native file ID and selected authorized
Terminal, creates a fresh input directory and checks transferred bytes.
`publish_terminal_file` snapshots a confirmed output path, uploads a new File,
checks its bytes and emits native attachment events. Neither deletes a source.
An incomplete post-upload step returns the actual result ID rather than hiding
the artifact or retrying publication. Auxiliary tasks and missing native context
fail before I/O. The configured transfer-size bound is additional to native limits.

## Qualification contract

1. Linux tests against actual HTTP/multipart boundaries: source preservation,
   exact bytes, native denial of foreign files/Terminals, inactive selection,
   transfer bounds, auxiliary tasks and uncertain publication without retries.
2. Ordinary chat starting with existing attachments, agent-controlled transfer,
   Linux processing, full source/output comparison and automatic durable attachment.
3. Reload and download after Terminal retirement; source hashes unchanged.
4. Verify final output-link handling and inspect the exact source installed.

## Evidence so far

The transfer tests execute inside the exact existing OpenWebUI runtime image on
Linux, with its installed aiohttp 3.13.5 and Pydantic 2.12.5. Transfer tests and
the extended verified-link Filter tests: **107 passed**. The HTTP test fixture
checks forwarded identity and failure handling; it is not a replacement for
real native access-control qualification.

The private Tool registry exposes only `stage_chat_file(file_id)` and
`publish_terminal_file(path)`. Request, metadata and event callbacks are injected
by OpenWebUI, absent from the model-facing schemas. Its private Terminal workspace
started empty. Two actual workbooks were uploaded through the normal chat input,
not the Terminal file manager.

The first ordinary-chat trial exposed a version-specific context bug in the
candidate: 0.9.6 captures `extra_params.__metadata__` before replacing the metadata
dictionary with one containing `terminal_id`. The candidate initially read the
stale dictionary and refused transfer before I/O. The agent disclosed failure;
no result was falsely published. The correction reads the original native HTTP
request's selected Terminal when metadata lacks it, verifies matching chat IDs,
then uses the native allowed-server list and proxy. No UI inference or server
fallback is used. A regression check covers the stale snapshot and a conflicting
chat identity. Both native input transfers subsequently succeeded in the same
ordinary chat, followed by complete processing and automatic publication.

The resumed ordinary-chat turn completed in 42 tool calls. The agent staged both
normal chat attachments, used native tasks and Linux execution, then called
`publish_terminal_file` itself. The native assistant attachment and download were
verified independently. Unlike the earlier pilot, neither source staging nor
result publication was performed by the operator.

Independent Linux OOXML comparison found all 23 sheets in the agreed order,
7,471 nonempty values with exact numeric equality (no rounding differences),
zero output formulas, matching number formats, 213 merged ranges, matching row
heights/column widths, and all 12 image placements with matching hashes/anchors.
All 974 cached formula values were retained. Original files and chat-upload copies
had unchanged hashes. This confirms saved values, not freshness of recalculation.
The source data, private chat/file IDs and workbook bytes are not included in Git.

After the full agent run, the final candidate added one bounded retry for transient
GET/download failures (429/502/503/504 or interrupted transport). Writes never
retry automatically. Linux HTTP tests cover recovery, stopping after the second
failure, permanent denial and uncertain writes. The final exact source was also
accepted by the native Tool registry. The full agent run predates only this read
retry addition; no transient-read fault was injected into the production service.

The private Tool, Skill, Terminal connection/container and retired credential
were removed after qualification. Chat history, source files and published results
were preserved. After Terminal retirement, chat reload still showed the native
attachment and authenticated download returned HTTP 200 with the same SHA-256.
The private Linux workspace remains as evidence, not a service.

The exact current source also passed the existing Linux integration command in
the deployed OpenWebUI image: **247 passed** (adapter, render, transfer and Filter
contracts; one existing Starlette/httpx deprecation warning). The transfer test
now resides in the already collected `services/officecli-openapi-proof/tests`
suite, with aiohttp 3.13.5 declared in that suite's test dependencies. This keeps
the candidate covered without changing the GitHub workflow file.

Reuse the upstream Filesystem upload branch if a separately qualified platform
upgrade replaces staging. Remove publication adaptation only when an upstream
operation provides the same durable Files/chat-attachment contract. A per-user
runtime manager is a separate deployment choice; an Enterprise-license question
does not block this private, single-user handoff qualification.
