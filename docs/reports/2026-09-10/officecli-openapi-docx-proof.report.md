# OfficeCLI OpenAPI DOCX proof

Revision: `2961f24`

## Observed native path

- A least-privileged `test` user enabled the temporary `officecli` OpenAPI connection in a normal chat; browser request carried `tool_ids: ["server:0"]`.
- OfficeCLI loaded its official Word skill, used official help and annotated inspection, and `apply-batch` returned HTTP 200 for two successive DOCX versions without a second upload.
- The second inspection resolved the first generated file from native message ancestry, not the original upload.
- `updated.docx` was attached to the assistant message, rendered as a visible chat file card, and downloaded through the normal UI.

## Artifact checks

- Word opened the downloaded DOCX read-only.
- The expected edited paragraph and latest section 3.2 heading are present.
- The ordinary fixture still has one table, non-empty header and footer, plus bold and italic runs.
- The sidecar has `OFFICECLI_SKIP_UPDATE=1` and `OFFICECLI_NO_AUTO_RESIDENT=1`; after processing, only `uvicorn` remained (no `officecli` or `soffice`).

## Acceptance limit

The selected model made two text-only false-success responses before explicit tool-call correction. The native file/version chain and visible-download seam are proven, but the unassisted natural-language completion policy is not yet accepted.
