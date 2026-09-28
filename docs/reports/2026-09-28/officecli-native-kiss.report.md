# OfficeCLI native workflow refactor

Status: release is not ready. The first candidate passed both CI jobs; the
always-visible workflow follow-up passed 210 local checks and three actual-CLI
checks. Its ordinary-chat qualification is recorded separately below. Production
remains unchanged. NDFL is excluded by explicit user scope.

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

### Follow-up: restore the author's always-visible tool context

The matrix exposed a methodological gap in this candidate: its bootstrap required
the model to call `help workflow` to obtain even the base tool workflow. OfficeCLI
v1.0.152 instead publishes the workflow, delivery gate and compact skill triggers
directly in its MCP tool description; only detailed guides/schemas stay lazy.
This is a verified delivery difference, not proof that it caused every model error.

The follow-up reads the installed `tools/list` while building OpenAPI and places its
unchanged description once in `get_officecli_help`, with an explicit transport
mapping. The Filter points to this already-visible description. It does not embed
business recipes or copy the text into every operation. Missing/malformed official
instructions prevent publishing an incomplete schema. The transport bootstrap is
915 characters; the official workflow is additional always-visible tool context,
not a claim that the total prompt has shrunk to 915 characters. Local checks: 210
passed. The rebuilt runtime image is
`sha256:ce5b86c99f2966bddf4de1cf57d96b72fb4e0bef8b3cb9b16e547d045ce8e535`;
three actual-CLI qualification tests passed in 68.816 seconds with network disabled,
read-only root and the production-sized 128 MiB noexec temporary filesystem.
Replaying the installed OpenWebUI `convert_openapi_to_tool_payload` and its native
schema resolver on that image's schema preserves the 4507-character help description
exactly, once across 13 operations (description SHA-256
`2cc8138deb372e3d3e3a2fcb395d33a5ee55f97dd5d370f259a2e014be52da55`).
This is native conversion evidence, not a captured outgoing provider request.
The first matrix below predates this follow-up and cannot qualify the changed
candidate; the separate follow-up matrix qualifies the rebuilt image.

### Required model coverage

Public scope was verified through `/api/models` authenticated as a disposable
ordinary user, using native public read grants. There are **nine** non-NDFL public
profiles. The two NDFL Pipes are explicitly excluded by the user. Admin-only GPT-6,
Claude Opus 5.5, Antigravity, Arena and TTS entries are outside this public scope.

Qualification used identical synthetic attachments and user prompts:
read-only discovery of two three-sheet workbooks, a Word table and a two-slide deck;
then a formula-based monthly workbook plus targeted Word and PowerPoint edits.
Production uses actual public IDs. Candidate uses private native Workspace Model
aliases on the same base providers and the identical candidate bootstrap. Candidate
alias results do not establish the post-release global Filter route.

| Public profile | Production observation | Candidate observation |
| --- | --- | --- |
| claude-opus-5 | Read correct; only XLSX delivered | Anthropic insufficient balance |
| claude-sonnet-4-6 | Read correct; edit interrupted by Anthropic balance error | Blocked on same provider |
| gpt-5.4-mini | No structural read; incomplete XLSX-only result | Structural tools used; no XLSX; wrong Word/PPTX targets and invalid links |
| models/gemini-3.5-flash | Read correct; Word/PPTX correct; XLSX monthly values zero | All three downloaded artifacts pass content/preservation checks |
| models/gemini-3.6-flash | All three downloaded artifacts pass content/preservation checks | Read and three artifacts pass; Excel recalculation correct, stored summary cache zero |
| office-documents (Claude Opus 5) | Blocked on shared Anthropic provider | Blocked on shared Anthropic provider |
| gpt-5.6-luna | Read/Word/PPTX correct; summary sums prices, yielding 100/500 | Read and three artifacts pass; Excel recalculation correct, summary cache absent |
| models/gemini-3.1-flash-lite | No structural read; wrong XLSX structure; no Word result | No structural read; incorrect XLSX, Word formatting and first slide changed |
| models/gemini-3.5-flash-lite | No structural read; XLSX source-sheet provenance incorrect; Word/PPTX correct | Read correct; only XLSX delivered, zero monthly values; no final answer |

These are single-run observations, not reliability estimates. Successful calls or
artifact counts alone are not acceptance. Checks download the native attachments,
resolve final-answer file references, compare original bytes, validate formula
values and all source rows, and compare unaffected Word/slide XML. The compound
three-output task is stricter than isolated per-format capability checks.

Microsoft Excel 16.0 independently opened read-only local copies and recalculated
formulas. Candidate Gemini 3.6 Flash and GPT-5.6 Luna produce 300/700 EUR after
recalculation, despite zero/absent cached values. They are not formula failures.
Production Gemini 3.5 Flash still produces zero (text wildcard against Excel dates);
production GPT-5.6 Luna produces 100/500 (price column instead of amount).
The two cache cases remain a preview limitation before an Excel recalculation.
One interrupted Sonnet artifact could not be opened in the Excel check; no pass is
claimed for that blocked run. This does not establish its failure's cause.

Native attachments were downloadable under the ordinary user's authorization.
Several answers nevertheless contain relative filename links or sandbox-prefixed
links instead of the supplied download URL. Artifact correctness and answer-link
quality are separate findings; the three successful artifact rows are not a claim
that every aspect of their final text is correct. Source files stayed byte-identical.

The native Anthropic response explicitly reports insufficient API credit. No
provider substitution or further requests to that provider are used to mask it.
For GPT-5.4 Mini the candidate exposes official help and actual structure, but the
model still issues unsupported commands, selects wrong object paths and stops.
No native tool-iteration-limit error was recorded. Do not add a task recipe or
blindly raise loop limits on this evidence.

KISS remains: installed OfficeCLI owns syntax/document semantics; native Open WebUI
owns authentication, file access and chat attachments; the existing adapter owns
transport limits only. No per-model business prompt, new client or core fork was
introduced for this matrix. Full public-model acceptance remains incomplete.

Next acceptance work: restore the existing Anthropic account and qualify its three
profiles; investigate why Gemini 3.1 Flash Lite ignores structural tools despite
the common bootstrap; qualify unsupported-command recovery and result verification
on GPT-5.4 Mini and completion on Gemini 3.5 Flash Lite. Trace the native provider
request/context before changing prompts. Any correction must stay generic and be
grounded in the installed author's workflow, not a spreadsheet-specific recipe.
Private QA aliases/connection and synthetic evidence are retained while this work
is unresolved. No global deployment or provider substitution was performed.

### Qualification of the always-visible workflow follow-up

The same six accessible base models were exercised through private profiles on the
rebuilt image. The three Anthropic profiles remain blocked by the explicit billing
error; no retry or provider substitution is counted as acceptance.

| Public base model | Follow-up observation |
| --- | --- |
| models/gemini-3.5-flash | Structural read and all three artifacts pass; Excel recalculates 300/700 EUR |
| models/gemini-3.6-flash | Structural read and all three artifacts pass; Excel recalculates 300/700 EUR |
| gpt-5.4-mini | Structural tools used; XLSX Beta source sheet incorrect and detail amounts hardcoded; missing Word output and incorrect PPTX edit |
| models/gemini-3.1-flash-lite | No structural read, incorrect claims about sheets/slides; unsupported edit commands and no outputs |
| models/gemini-3.5-flash-lite | Structural read; only XLSX returned, monthly values remain zero after Excel recalculation; no final answer |
| gpt-5.6-luna | Read, Word and PPTX pass; XLSX omits the requested source-sheet provenance |

The final artifact result is two passing profiles, four failed/incomplete profiles,
and three provider-blocked profiles. A blank default Sheet1 is recorded as a
cosmetic observation, not a task failure: the prompt did not prohibit extra empty
sheets. This correction to the QA assertion does not change the failed profiles;
their source provenance or requested outputs remain incorrect/incomplete.

Test validity: one run with a detached follow-up ancestry was excluded. Three more
private-profile follow-ups lost OfficeCLI availability after page reload and are
excluded from model-quality conclusions. A native metadata receipt proved that one
diagnostic turn contained only built-in tools; another contained OfficeCLI with the
exact 4507-character description. This establishes a QA route discrepancy, not its
frontend cause or a general production defect.

Those three cases were repeated using the candidate's existing Filter code on
every request, targeting only the private aliases and candidate connection. Native
metadata receipts for Gemini 3.6, 3.5 Lite and GPT-5.6 Luna prove the expected tool set and exact
description hash on both read and edit turns. No public settings or Open WebUI core
were changed. This temporary diagnostic Function is not a second production owner.

A separate bounded read-only probe disabled native automatic file context on the
private Gemini 3.1 Lite profile, then restored it. The model used 13 structural tool
calls instead of zero and recovered sheet/slide names, but still omitted March data
from one workbook. Competing extracted-text context is a supported hypothesis, not
a proven universal cause or an accepted fix. Public RAG remains unchanged.

The subsequent full-task diagnostic changed only the native `file_context`
capability to false for the two private Lite aliases. It retained built-in tools,
the same official guidance, source attachments and task, and the candidate Filter
on every request. Both profiles used structural tools (11 and 17 read calls) and
returned three files. Gemini 3.1 Lite still omitted March/Word-row content in its
read answer and produced incorrect XLSX, Word and first-slide edits. Gemini 3.5
Lite's read answer and all three artifacts passed; Excel independently recalculated
300/700 EUR, with correct provenance and unchanged Word/slide elements.

QA correction: the request specified EUR but did not require a currency number
format. An explicit EUR column heading satisfies that requirement; the earlier
format-only assertion was overstrict. The corrected assertion was reapplied to
all saved matrices. The principal matrix remains two pass, four incomplete/failed,
three provider-blocked. The tools-only diagnostic success is a separate configuration
and must not be substituted into that matrix.

Both private profiles were restored and the diagnostic Function disabled after
the experiment. [Open WebUI documents this native tools-only mode](https://docs.openwebui.com/features/chat-conversations/rag/),
but one successful diagnostic is not sufficient evidence to disable automatic file
context across public general-purpose models or to promise all-model reliability.

These results do not establish reliable support across all public models. Keep
guidance shared and official; do not add model-specific document recipes to turn
the failing rows green. Native attachments, source preservation, file content and
the final user answer remain separate acceptance checks.

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
