# OfficeCLI capability context

The adapter previously admitted only 18 help topics and exposed DOCX annotated text,
XLSX cell views, and PPTX shapes. An XLSX picture inventory was unavailable through
the read-only tool. The Filter also told the model to stop after successful
composition, even when the request included further changes. These restrictions
prevented the installed CLI's capabilities from being represented accurately.

## Change

- The installed OfficeCLI owns its element catalog and operation/property help.
  `get_officecli_help` accepts a format, format/element, or format/verb/element
  topic, including newly added elements. Bare supported command names return
  command usage. Existing `docx view` and `xlsx view` aliases remain compatible.
  Flags, paths, control characters, and shell syntax cannot be help topics.
- The existing three inspect operations now expose native `query` and `get`.
  Selectors discover actual paths, including pictures across workbook sheets;
  the adapter never manufactures paths. Native file/session authorization remains
  under the existing OpenWebUI client. Reads do not publish modified artifacts.
- Query responses retain the native match count and complete object properties.
  Adapter pagination reports offset, returned count, total, and next offset.
  Oversized nodes/views are explicitly withheld, not presented as empty results.
- The Filter supplies a short discovery route, keeps simple creation examples,
  and allows requested edits and verification on a generated `result_file_id`.
  It distinguishes cell outlines from drawing inventories and instructs descending
  index order for repeated removals. Full skills remain on demand.

Permanent instruction size is 4,223 characters, compared with 3,690 previously.
The conditional multi-XLSX instruction remains 1,528 characters. No full skill
is injected automatically. Existing model selection, auxiliary-task guards,
tool attachment, and no-reasoning valves are unchanged.

This follows the project's documented progressive help and verification workflow:
[built-in help and verify/fix example](https://github.com/iOfficeAI/OfficeCLI#built-in-help),
[query](https://github.com/iOfficeAI/OfficeCLI/wiki/command-query),
[get](https://github.com/iOfficeAI/OfficeCLI/wiki/command-get).
Runtime qualification uses pinned OfficeCLI 1.0.152 rather than assuming that
current upstream examples have identical JSON envelopes.

## Evidence and limits

- 182 adapter and Filter tests passed; Ruff correctness checks and `git diff --check`
  passed. Regression coverage includes existing creation/composition, session
  rejection, file ambiguity, atomic failure, and large-workbook context limits.
- The repository Dockerfile built an isolated candidate image. The qualification
  script runs the installed package from `/tmp`, with network disabled and the
  filesystem read-only except for a temporary fixture directory.
- Real CLI qualification discovered pictures in synthetic XLSX, DOCX, and PPTX
  through the actual inspect routes, obtained an actual picture node through get,
  and exercised the previously blocked help topics.
- The XLSX fixture had an empty first sheet and nine pictures across two other
  sheets. Removal used the returned paths in reverse order through apply-batch.
  Readback found zero pictures; independent ZIP inspection found no image media.
  Cell values, formulas, and sheet order were preserved; original source hashes
  were unchanged. The native-file transport in this isolated test is local and
  synthetic, not a real authenticated OpenWebUI session.
- The candidate OpenAPI schema was passed through the installed OpenWebUI 0.9.6
  resolver and cleaner. Help descriptions and query/get/selector/path/depth/page
  arguments survived conversion. This is schema-delivery evidence, not a captured
  provider request or an ordinary-chat acceptance result.

Production deployment and ordinary-user browser acceptance are separate pending
release steps. Deploy both the Tool Server image and Filter, refresh the native
Tool Server specification cache, then verify an ordinary chat using synthetic
attachments. Check the final attachment independently; a successful tool call
alone does not establish that the model satisfied the user's request.

The reported user's original workbooks and generated files were not modified.
