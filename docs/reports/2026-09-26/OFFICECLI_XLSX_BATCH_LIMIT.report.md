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
- These checks establish adapter/CLI behavior, not a full model/chat acceptance
  or completion of the original 29-workbook task.

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
