# OfficeCLI native workflow refactor

Status: implementation, isolated candidate acceptance and OfficeCLI CI passed;
repository-wide CI and shared release pending. Production remains unchanged.

## Goal and ownership

The agent must discover and use the installed OfficeCLI capabilities for user-defined
XLSX, DOCX and PPTX tasks, without scenario recipes embedded in the integration.

- Document semantics, syntax, guides and validation -> installed OfficeCLI ->
  official help/skills/commands/results -> agent.
- User identity, authorized source files, chat ancestry and delivered attachments ->
  Open WebUI -> existing Files/auth/chat APIs -> OfficeCLI transport adapter.
- Temporary paths, process limits and response size -> adapter -> explicitly documented
  transport constraints -> agent. These must not choose business content or layouts.
- Selection, grouping and acceptance against the request -> agent using source
  evidence -> user-visible result. The adapter must not substitute monthly stacking.

The current OpenAPI connection is a native Open WebUI integration surface. Retain it
and its authorized file owner. A wholesale MCP migration would require a proven
benefit and the same file-access/delivery boundary; protocol replacement is not an
acceptance criterion.

## Slices

1. Remove scenario instructions and the custom spreadsheet composition route/engine.
   Replace recipe assertions with observable routing and read-only behavior checks.
2. Preserve installed documentation and diagnostics, make bounded inspection complete
   through explicit continuation, and remove unrequested document normalization.
3. Reconcile exposed commands with official guidance, verify real installed-CLI
   operations and then ordinary-chat XLSX/DOCX/PPTX outcomes.

## Acceptance

- Read-only questions identify actual structure without publishing a document.
- Multi-file decisions use source contents, not filenames or attachment count.
- Official documentation remains authoritative and available on demand.
- Warnings/errors and omitted result content are recoverable and explicit.
- Source bytes and native permissions are preserved; results use native attachments.
- Unfamiliar spreadsheet, Word and presentation tasks pass content/visual checks.
- CI and lower-level checks are reported separately from ordinary-chat acceptance.

Production remains on PR #539 until a concrete candidate is verified and release is
authorized. The earlier authorization for PR #535 is not a standing release grant.

## Baseline evidence

Source: d7aa1672ef6f45e4641b34f0872c34b289371851.
The deployed Filter and normalized application source match that revision.
Official reference: OfficeCLI v1.0.152 `McpServer.cs` and bundled skills; Open WebUI
native OpenAPI tools. Private chat/source evidence remains outside this repository.

- [Installed-version tool instructions](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/src/officecli/McpServer.cs)
- [Official skill entrypoint](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/SKILL.md)
- [Open WebUI native tools](https://docs.openwebui.com/features/extensibility/plugin/tools/)

## Delivered changes

- The Filter's 939-character bootstrap (previously 6552 characters, plus a conditional
  1528-character multi-XLSX instruction) directs the agent to the installed author's
  unchanged MCP tool description, lazy skills and targeted help. It describes file
  IDs, copy-on-edit and nonresident execution, without document/task recipes.
- Removed the custom openpyxl composition engine and route, its validation owner,
  automatic DOCX normalization, implicit table inspection and local PPTX semantic
  validators. Native OfficeCLI now owns the changed document operations/validation.
- Preserve successful stderr diagnostics and failed native output. Large reads have
  recoverable node/text continuation instead of withholding the structure.
- Expose native view bounds, HTML/forms/SVG modes and screenshot ranges through the
  existing adapter. No Open WebUI core changes or new file/state owner.

## Verification on the candidate

- Local integration/unit checks: **209 passed**; `git diff --check` passed.
- Built the actual runtime Dockerfile, then installed test-only dependencies into
  a separate qualification image. No source-path override. **3 real-CLI tests
  passed in 66.325 seconds** with networking disabled, read-only root, 1 GiB memory
  and a 128 MiB temporary filesystem.
- Qualification includes exact official instruction discovery; all 137 names in
  a real multi-sheet workbook in order; all-format object reads, native validation
  and rendering; targeted inactive-sheet rendering; XLSX picture removal without
  losing text/formulas; rejected native PPTX commands without publishing a file.
- Candidate runtime image:
  `sha256:3c471772b59672147cf90bdc86439042058732beaa9be2c6aa4651acd127b092`.
  Installed application SHA-256:
  `4af043ba7ca8d3c91d245ba8c17bbba071c002d76a90d31b5396698a6cccac91`.
- An earlier diagnostic run imported the old installed package and was discarded.
  The final qualification above exercises the freshly built installed candidate.
- [OfficeCLI CI](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/36386957597)
  passed on implementation head `11f218913705d4a7424c784a02464b6151ff5daa`.

Ordinary authenticated UI chats used synthetic files, a private native OpenAPI
connection to that image and a private Workspace Model based on `gpt-6-sol`.
Its system instruction is the exact candidate Filter bootstrap. The production
connection, global Filter and public model configurations were not replaced.

| User task | Independently checked result |
| --- | --- |
| Analyze two workbooks without editing | All six sheets identified; actual February/March dates distinguished from misleading filenames; no mutation calls or generated attachments. |
| Create a monthly summary and details with formulas | Native `summary.xlsx`; four correct source rows; February 300 EUR, March 700 EUR, total 1000; source filename/sheet provenance; formula text and cached values checked; both original files byte-identical. Readable rendered details verified. |
| Edit and extend an existing Word table | Beta quantity 5 and new Gamma quantity 7; Alpha, heading, Table Grid style and following paragraph retained; native attachment and rendered page checked; original bytes unchanged. |
| Change one text on slide 2 | `Revenue 200`; first slide and all other package parts unchanged except OfficeCLI's modification timestamp. Slide 2 XML differs only in requested text; both slide images checked; original bytes unchanged. |

A further ordinary-chat check used `models/gemini-3.5-flash-lite` through a private
Workspace Model with the same instruction/connection. It identified all 137 sheets,
the correct first/last three names and three raster images on sheets 000/070/136.
On a follow-up it removed those images and delivered a native attachment. Independent
download inspection confirmed all 137 names/order/cell values, no `xl/media/` parts
or remaining sheet pictures, and byte-identical source. The model did not itself
perform a post-edit inspection; do not confuse our artifact check with model QA.

The initial Gemini test profile had an arbitrary ID and produced an empty response
without tool calls. Live source inspection confirmed that the pre-existing Google
protocol overlay recognizes IDs starting with `models/gemini-`. Repeating with an
ID in that namespace succeeded. That existing alias limitation remains; no provider
overlay or global routing was changed by this refactor.

The XLSX agent initially used extra quotes around two sheet names, received native
errors with available sheet names, corrected the requests and continued. No special
quote-handling recipe was added to the integration.

## Release boundary and remaining limits

This covers all three formats on GPT and large-XLSX discovery/editing on Gemini,
not a new qualification of every published model. The global Filter path still requires a direct-model smoke
test after release; candidate chats test the native tool/file loop with the same
bootstrap delivered by private model parameters.

The removed `compose_office_spreadsheets` route is an intentional compatibility
break. OfficeCLI's native `merge` is template substitution, not cross-workbook
composition. Arbitrary lossless workbook consolidation is not claimed. Existing
explicit transport bounds (batch sizes, object depth and attachment-image mapping)
remain; this is not a claim that every CLI operation is remotely exposed.

Release after CI and authorization:

1. Preserve current image, Function source/valves/Active/Global, native tool-server
   connection and `office-documents` parameters in a private rollback record.
2. Replace only the OfficeCLI sidecar and existing Filter, preserving model allowlist,
   native permissions and connection identity. Re-read and compare their identities.
3. Remove the legacy DOCX-only `office-documents.params.system` instruction while
   retaining its other settings; the shared Filter owns this integration context.
4. Refresh the existing native connection's schema. Run a new ordinary direct-model
   chat for read-only discovery and a delivered/verified edit; check a follow-up turn.
5. On failure restore the recorded sidecar, Function and model parameters. After
   acceptance remove only task-created private QA connection/model/container.
