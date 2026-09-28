# Office workflow completion qualification

Status: qualification completed with explicit delivery limits; candidate not deployed. No production OfficeCLI sidecar, shared Filter, provider connection or core has been replaced. Test chats retain their files and tool evidence. Local Windows is used for source editing/browser/SSH only; execution and document checks run on Linux.

## Accepted outcome and owners

- Task scope, source inventory, grouping, preservation and completion criteria → user and agent → native Skills/Tasks → file operations. A plan is not proof of completion.
- Source access, native file IDs, publication and downloads → OpenWebUI Files/chat APIs → existing OfficeCLI transport → user attachment.
- Document semantics and rendering → pinned OfficeCLI 1.0.152 → native commands/results → existing adapter. The adapter does not become a workbook merge engine.
- Provider model discovery → OpenWebUI connection configuration → model catalog → native completion loop. A document tool cannot retry a model lookup after that loop terminates.
- Displayed link → successful tool publication receipt → existing Filter outlet → assistant prose. This is a representation adapter; no new file, provider or state owner.

## Observations and discriminating checks

### Excel

The previous copy/remove-sheet experiment failed on stale calculation-chain references. It does not disprove building a new workbook from cached values. Original inputs were preserved. Earlier value transfer was verified for two of 23 sheets, not the full source set.

A fresh private-model trial loaded the revised native workflow and inventoried both inputs. It created 23 named sheets, wrote only 13 of 7,471 stored cell values, then stopped after a successful mutation. The response correctly disclosed missing values/formats and 12 image placements and linked the partial file. Transfer and verification remained pending. Both source hashes remained unchanged. This is **not accepted completion** and does not establish that another instruction would solve the execution gap.

The present adapter exposes individual/range reads and batches of cell operations; native range `set` broadcasts formatting, not a value matrix. A generic native Linux execution capability is being investigated before considering any scenario-specific backend operation.

### Word

The original run stopped with `Model '' was not found`, preceded by model-list connection errors. In deployed 0.9.6, the missing-model exception omits the requested name; the blank string does not prove an empty requested model ID. A transient discovery failure is supported as a hypothesis, not a proven provider outage.

One fresh-context continuation recovered the saved document. It made 94 tool calls and published 11 versions, repeatedly reopening a completed verification task. The trial was stopped; it is not an autonomous success. Source-bound XML checks found all 12 sections/tables and values in a saved version, while screenshots showed apparent table duplication and footer overlap.

The pinned upstream renderer has a page-1 screenshot shortcut which skips pagination. Later page screenshots paginate. Comparing the **same unchanged DOCX** on Linux with native `view screenshot --grid 2` removed the apparent duplicate table and footer overlap. A heading separated from its table remained visible. Therefore neither blaming all edits on gratuitous polishing nor declaring the full layout accepted is justified.

Sources: [pinned pagination shortcut](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/src/officecli/Handlers/Word/WordHandler.HtmlPreview.cs#L1352), [native grid implementation](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/src/officecli/CommandBuilder.View.cs#L294).

### Delivery links

The completed PPTX existed on disk and in the assistant's native attachments; authenticated content download returned HTTP 200. The tool returned a correct relative download URL. Assistant prose added `sandbox:`. Native attachment cards are visible after loading the chat. This is a malformed displayed link, not an invented file.

## Candidate slices

1. Existing Filter outlet repairs only an observed malformed Markdown destination whose exact file ID, native result-file ID and download URL agree in a completed publication tool result in the current assistant turn. Unknown URLs and tool evidence remain unchanged; this is not a general hallucination detector.
2. Native artifact-workflow Skill: preserve the agreed method, record progress/remaining parts, distinguish temporary read failures from uncertain mutations, retain the latest result, investigate repeated defects, and deliver an explicitly partial artifact if blocked. The prompt-only trial failed; workflow plus native Linux execution completed the full Excel trial described below. This is not a general success guarantee across models and documents.
3. Existing render operation exposes native DOCX/PPTX `grid`, preserving read-only file access, PNG bounds and single-render concurrency. Single-page rendering remains available for detail. No HTML/OOXML patch or upstream fork.
4. Investigate native model-ID configuration and native Linux execution/file transport. Do not add a second completion loop or bespoke Excel composition endpoint.

## Evidence so far

- Linux isolated Filter suite: 84 passed.
- Replay of the actual completed PPTX turn through candidate outlet: malformed link corrected, all non-message tool output unchanged. Historical chat was not rewritten.
- Linux native grid comparison on the unchanged Word artifact: visual false duplication/overlap resolved; remaining heading/table split not hidden.
- Private Excel ordinary-chat run: failed completeness, delivered an honest partial artifact. This is a useful negative result, not release acceptance.
- Built the actual adapter runtime candidate and qualification images on Linux. Installed adapter suite plus Filter suite: **224 passed**. The one warning is a Starlette/httpx deprecation.
- Executed the installed candidate render endpoint with the real CLI against the unchanged saved Word document: native `grid: 2` returned a 1,380 × 1,920 PNG; source SHA-256 stayed identical.
- A private ordinary-chat grid check subsequently reached the candidate through the native tool-server connection. Initial rendering failed in a QA container with added process/CPU limits; after recreating that QA container with the production resource settings, a bounded retry returned HTTP 200 and the model identified the three-page layout, absence of duplicate UNIT05/footer overlap, and the actual heading/table split. No document mutation was requested or performed. The first failed QA setup is not evidence that the browser was uninstalled.

## Native Linux execution pilot

The official Open Terminal `0.14.0-slim` image was prepared for the private administrator trial, pinned to `sha256:ba7a67129bbaf8618887eb6283d7e351275e2838c0751bbafebbce6b22938687`. Its installed libraries include openpyxl 3.1.5, python-docx 1.2.0 and python-pptx 1.0.2. The service has a separate task workspace, no production file-volume or Docker-socket mount, no published host port, a read-only root, dropped capabilities, and 512 MiB / one CPU / 128 PID limits. It shares the existing application network; this is filesystem/resource separation, not network or multiuser isolation.

The native private Terminal connection is visible through the standard chat selector and file manager. Source files were copied through the authenticated OpenWebUI file download and native file-manager upload path, without Office processing on Windows.

The full ordinary-chat Excel trial **completed autonomously**, with 45 tool calls including inspection, native tasks, Python execution, verification and `display_file`. Independent Linux OOXML checks of the final file found all 23 sheets in the agreed order, all 7,471 nonempty stored values with exact numeric equality, zero remaining formulas, matching number formats, 213 merged ranges, matching row heights and column widths, and all 12 image placements with matching image hashes and anchors. All 974 formula caches were preserved as values; both original source hashes stayed unchanged. The agent's 9,785-cell comparison also counted blank/styled cells, so it is not a conflicting nonempty-value count.

The ordinary file viewer opened the workbook and its download control was exercised. An authenticated download was bound to the independently checked final SHA-256. The verified output was then **operator-published**, through native Files upload and attachment events, into the test chat so it survives pilot cleanup. That final durable attachment is not evidence of automatic agent publication between Terminal and Files. No new cross-store adapter was added. The trial also used explicit native file-manager input upload: ordinary chat attachments are not proven to appear automatically in Terminal on deployed 0.9.6.

This establishes a usable native Linux bulk-execution path on the full representative inputs. It does not establish multiuser filesystem isolation, automatic chat/Terminal file handoff or public deployment. The final Skill draft additionally documents these transport boundaries and bulk execution; those clarifications postdate this successful trial.

### Runtime incident and rollback

At 14:43:07–08 UTC, the kernel killed the existing OpenWebUI process at its 6 GiB memory limit; Docker restarted it. The causal request has not been established. This happened before the Terminal trial and must not be attributed to Terminal execution.

Later, connecting OpenWebUI to an additional internal QA network was followed by public-route 504/timeouts while its internal health stayed HTTP 200. Traefik had no explicit Docker network selection. The additional connection was reverted and Traefik restarted; public version, authenticated chat and file-download requests recovered to HTTP 200. The observed cause is consistent with proxy selection of an unreachable extra-network address; the exact cached destination was not captured. The extra QA network was removed. The Terminal alone is now on the existing application network, with a private network alias under the existing local proxy-bypass suffix. No production WebUI network/configuration was retained from that experiment.

## Runtime and isolation

OpenWebUI has 23 accounts and no Enterprise license configured. Official Open Terminal guidance allows the free built-in multi-user mode only for a small team whose users are trusted at the same level: home directories differ, while the kernel, process list, network, root-capable system state and resource pool remain shared. Official Terminals provisions per-user containers and requires an Enterprise license; mutually untrusted users require its Kubernetes backend plus a NetworkPolicy. The pinned free-mode Compose candidate is therefore prepared but not activated until the trust boundary is explicitly accepted. Sources: [multi-user comparison](https://docs.openwebui.com/features/open-terminal/advanced/multi-user/), [Terminals deployment and license](https://docs.openwebui.com/features/open-terminal/terminals/).

The deployed OpenWebUI 0.9.6 also predates the fix for CVE-2026-59224 / GHSA-j657-m4c4-24jq. Its WebSocket terminal route interpolates a decoded session ID ahead of the authenticated `user_id` query, allowing a normal user to inject another identity. A fail-fast overlay now backports the upstream 0.10 behavior, rejects ambiguous delimiters and percent-encoded follow-up decoding, and quotes the session ID as one path segment. The exact 0.9.6 base image built successfully on Linux, the patched router compiled, a second patch pass reported `already_patched`, and an isolated candidate container returned `{"status":true}` from `/health`. The overlay must be removed when the base image reaches 0.10.0 or newer. This closes the proxy query-injection route; it does not turn the free shared container into a security boundary. Source: [upstream advisory](https://github.com/open-webui/open-webui/security/advisories/GHSA-j657-m4c4-24jq).

Working copy: `agent/office-workflow-completion-20260928`, based on `b0a09dab`; unrelated original workspace changes preserved. Task-created private Workspace Model, non-global Filter, private Skill, Terminal/render connections and two test containers were removed after qualification. The extra network had already been removed. Native chat/file history and the durable verified Excel attachment were retained and checked after cleanup. Private Linux evidence/workspace and candidate images remain for review and reproducibility; they are not active services. OpenWebUI is healthy, on its original network, with restart count 3; the production OfficeCLI container was not restarted.

Runtime candidate image manifest: `sha256:f62dea3c8b02e4f03fa10b50f5404df303d286f5c91ce1049369c66a5953b9df`. Qualification image manifest: `sha256:42bd4d3ad7175ca5d86b73dfed779466dc0f19cb1c4aa91cdc3933dd4407c03c`. The shared-route Filter candidate is `2.1.0-native-terminal-handoff`.

## Delivery decision

The narrowly scoped code candidate contains verified-link adaptation, native whole-document rendering, a native Skill draft, a generic native file-transfer Tool and operational guidance. It introduces no document composition endpoint, custom planner, second completion loop or provider client.

Full Excel content completion has been demonstrated through native Linux execution. The first pilot above used operator input/output transfer. A subsequent ordinary-chat qualification closed that gap: the agent staged native chat attachments and published the fully verified result as a durable native attachment itself. See [Terminal handoff qualification](terminal-file-handoff.report.md) for the version-specific gap, thin adaptation, full source comparison and failure handling. Multiuser execution and shared deployment remain unqualified; the private pilot is not a finished public service. Shared deployment and provider-catalog changes have not been performed.

The installed OpenWebUI already supports explicit connection model IDs and terminal tools. Official references: [manual model IDs](https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/), [Open Terminal integration](https://docs.openwebui.com/features/open-terminal/setup/connecting/). Current documentation may describe capabilities newer than deployed 0.9.6; verify deployed source before using them.
