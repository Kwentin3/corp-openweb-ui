# Large-file OfficeCLI workflow — qualification in progress

Product target: ordinary OpenWebUI chat consumes many uploaded workbooks and
returns a verified native output attachment. For the 29-workbook case the owner
explicitly requires live formulas and dependencies, not a values-only snapshot.
No production change or product acceptance is claimed by this working report.

## Ownership and smallest seam

| Meaning | Owner | Contract | Consumer |
| --- | --- | --- | --- |
| User, chat, source access, file storage | OpenWebUI | Existing authenticated Files/chat APIs | Existing OfficeCLI Tool Server |
| Office inspection, existing create/edit operations | Pinned OfficeCLI | CLI view/help/batch/validate | Existing adapter |
| Cross-workbook stacking and address relocation | Narrow XLSX composition module | Explicit source IDs and destination sheet names; complete source-derived file | Tool endpoint |
| Planning and choosing sources | Selected chat model | Native tool calls and small receipts | User |
| Final attachment | OpenWebUI | Existing upload/attach client | Ordinary chat UI |

The composition module is a transformation owner, not a second storage owner.
The endpoint only authenticates, downloads, calls the transformation, validates,
and publishes. No provider client, database, queue, generic workflow engine, or
OpenWebUI core patch is introduced. Financial data must stay in private files;
only synthetic fixtures and aggregate evidence belong in Git.

## Observed gaps

- The existing spreadsheet inspection returns an unrestricted annotated dump.
  In the original chat the latest 29 successful inspections stored approximately
  3.04 million serialized result characters. The final assistant text was empty;
  the exact provider continuation failure is not established.
- Native `outline` plus sheet-qualified `view text --range` provides bounded
  decision context. Oversized results must be explicitly withheld, not silently
  truncated and represented as complete.
- OfficeCLI 1.0.148 `dump`/`batch` round-trip on a source copy lost the text of
  262 shared-formula children. Official 1.0.152 restored all 590 formulas on that
  same workbook. This is a component experiment, not a release qualification.
- OfficeCLI offers no confirmed native cross-workbook operation that stacks
  sheets and relocates all dependencies. A full dump/replay is not that operation.
- Source inspection found 467 sheets, 19435 formulas, 37 pictures, 18 external
  link records and 37 error-typed source cells (including formula caches).
  Some external workbooks are absent. Preserve these links; never infer that a
  similarly named upload is the same revision or silently substitute values.

## Candidate behavior and boundaries

One destination sheet per explicitly selected source workbook. Stack all source
sheets in their original order with labelled blocks and one blank separator row.
Reserve referenced blank rows so a formerly empty reference cannot accidentally
point into the next source block. Relocate absolute as well as relative addresses:
this is movement of a dependency, not Excel fill/copy semantics.

Use openpyxl's existing parser/writer and formula tokenizer for the missing
transformation; preserve original external links and their cached values. Formula
caches are retained from source OOXML after writing, without calculation or
fabrication. Source bytes remain unchanged. Unsupported formula/resource semantics
must fail before publication. A successful result must distinguish preserved
source errors and external dependencies from introduced errors.

The isolated built candidate composed and independently verified all 29 copies in
112.23 seconds under a 1 GiB / one CPU container limit. Child-process peak RSS was
229272 KiB (about 224 MiB). The production worker also has a 768 MiB address-space
limit and a 180-second parent deadline; only one composition runs at a time.

Independent reverse-reference comparison passed for 72361 nonempty cells and
their saved values, all 19435 formulas, 4517 merged ranges, and all 37 pictures
(including image-byte hashes). OfficeCLI 1.0.152 validation of an output copy
returned zero schema errors. Original 37 error-typed caches/cells and 18 external
link records remain distinguishable from introduced errors.

The source comparison found and fixed numeric serialization precision loss by
retaining source numeric XML values. The schema validator found two openpyxl
drawing serialization issues: an optional empty geometry-guide list inherited the
wrong namespace, and copied pictures reused IDs inside the combined drawing.
Omit only the empty optional list and assign unique IDs in the existing drawing
objects. Do not suppress schema validation or change picture bytes.

## Primary references

- [OfficeCLI pinned XLSX guidance](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.148/skills/officecli-xlsx/SKILL.md)
- [OfficeCLI shared-formula issue and maintainer fixes](https://github.com/iOfficeAI/OfficeCLI/issues/391)
- [OpenWebUI large tool results discussion](https://github.com/open-webui/open-webui/discussions/15884)
- [OpenWebUI inlet-loop maintainer response](https://github.com/open-webui/open-webui/discussions/24541)
- [openpyxl formula tokenizer](https://openpyxl.readthedocs.io/en/stable/formula.html)
- [openpyxl worksheet limitations](https://openpyxl.readthedocs.io/en/stable/tutorial.html)

## Remaining acceptance

Independent full source/result comparison, supported/unsupported synthetic
fixtures and negative mutation checks; endpoint authentication and failure
cleanup; exact candidate image checks; native browser completion on published
supported profiles; full original-source scenario through a copy of the old chat;
CI, documentation, release identity and cleanup. Preserve the original chat.
