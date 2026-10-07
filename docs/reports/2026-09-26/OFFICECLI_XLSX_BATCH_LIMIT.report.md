# XLSX batch limit correction

The 66-item request in issue #527 was rejected by the adapter's Pydantic
`max_length=64`, before OfficeCLI execution. This is a separate failure from the
later OpenWebUI OOM; removing the validation failure does not establish the OOM cause.

Both XLSX create and apply-batch now accept 1–256 items, matching the existing
bounded PPTX policy. The number is an adapter resource policy, not an upstream
OfficeCLI limit. The shared OpenAPI schema advertises it to all supported models.
The adapter passes the entire ordered batch to one OfficeCLI invocation with
`--stop-on-error`. It does not split, truncate, retry or use `--best-effort`.
Failed work is not uploaded or attached.

Upstream's [batch documentation](https://github.com/iOfficeAI/OfficeCLI/wiki/command-batch)
describes single-open/single-save execution and atomic rollback since 1.0.137.
The deployed, pinned version is 1.0.148. Keeping one atomic invocation preserves
that behavior and avoids exposing a partially constructed workbook.

## Evidence

- Adapter suite: 54 passed, including create/apply at 66 and 256 commands,
  rejection of 257 before side effects, OpenAPI maxItems, and failed-batch
  publication prevention. Native file boundaries are substituted in these tests.
- `services/officecli-openapi-proof/tests/verify_xlsx_large_batch.py` ran against
  real OfficeCLI 1.0.148 in an isolated, network-disabled container with 512 MiB RAM.
  It independently read every generated XLSX cell, including the final operation,
  for 66 and 256 commands. A failing last command left the workbook byte-identical
  despite a preceding change to A1. Both cases passed.
- These component checks alone do not establish model/chat acceptance.
  The later live qualification below covers the 66-command create/edit path,
  not completion of the original 29-workbook task.

## Release and native chat acceptance

[PR #531](https://github.com/Kwentin3/corp-openweb-ui/pull/531) merged as
`8632281ddee0c818a570e5c75c5a74a2a684d9dd`; required CI passed in 18m13s.
The unchanged native Function suite also passed (73 tests; 127 tests together
with the adapter suite). The candidate's 54 adapter tests and real-CLI check
were repeated inside the built Linux image before deployment.

The deployed image is
`sha256:330dc496d716fed302bc6e69e8d329a78086e4890b64fd9744761d6dfdd16362`.
The Tool Server schema was refreshed using the native configuration endpoint;
connection settings remained identical. Main OpenWebUI container, image and
restart count were unchanged. See the [release runbook](../../infra-ops/officecli-openapi-docx-release.md)
for deployment paths and rollback.

GPT-6 Luna was exercised through the normal browser chat UI with an administrator
session. This is not an ordinary-user permission-matrix retest.

| Operation | Native result | Independent artifact check |
| --- | --- | --- |
| Create, 66 commands | One attached XLSX, downloaded through native files API | 33 named sheets with correct A1 values; default Sheet1 empty |
| Follow-up edit, 66 commands | One apply-batch call and a new native attachment | All 66 A1/B1 values correct; original file hash unchanged |

During creation the model made two invalid-syntax attempts, consulted official
help, then succeeded. No partial file was published. This was successful recovery,
not first-attempt success. Artifact SHA256 values:

- Create: `529965cae13339407c7b8caa2fb950cd1e5ee5dc8de48e8928fc23ab5f349c04`.
- Edit: `1444e289d1aad92b43f6a47aa252ab476f15770c9a5a5e5a92cdb9dbd80f2168`.

All 12 supported profiles use the same server/schema. The other 11 profiles
were not individually re-run for this limit change. Synthetic chat/files,
staging archive, temporary worktree and task branch were removed after verification.
Deployed source and the rollback image are intentionally retained.

## Remaining boundary of issue #527

All 29 source attachments were readable through their existing native file IDs.
The user's request is one monthly worksheet per source workbook, combining its
daily sheets. Raising the command limit does not implement that transformation
or prove preservation of its values, formulas, merged cells and drawings.

The official [pinned XLSX skill](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.148/skills/officecli-xlsx/SKILL.md)
documents bulk import and dump/replay. The pinned
[Excel copy implementation](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.148/src/officecli/Handlers/Excel/ExcelHandler.Add.cs)
copies rows/columns within a workbook; it is not a cross-file whole-sheet merge.
Do not treat a generated list of sheet names as merged source data, or implement
an unqualified dump/replay transformation that silently loses workbook resources.
The original chat and attachments were preserved. Issue #527 remains open.
