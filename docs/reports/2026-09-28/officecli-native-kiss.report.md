# OfficeCLI native workflow refactor

Status: implementation in progress; not deployed or product-accepted.

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
