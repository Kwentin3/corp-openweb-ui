# Large-file OfficeCLI workflow — release qualification

Product target: ordinary OpenWebUI chat consumes many uploaded workbooks and
returns a verified native output attachment. For the 29-workbook case the owner
explicitly requires live formulas and dependencies, not a values-only snapshot.
Implementation `04f940c4` is installed after required CI passed; the primary
OpenWebUI container was not restarted. It includes the follow-up source-resolution
fix over the fully qualified composition baseline `19a8bf0c`.

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

The exact `19a8bf0c` image composed and independently verified all 29 copies in
116.27 seconds under a 1 GiB / one CPU container limit. Child-process peak RSS was
227824 KiB (about 222.5 MiB). The production worker also has a 768 MiB address-space
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

## Browser evidence

All twelve currently published, supported profiles exercised the new native
composition route. Nine used a temporary ordinary-user account: Claude Opus 5,
Claude Sonnet 4.6, GPT 5.4 Mini, Gemini 3.5 Flash, Gemini 3.6 Flash,
Office Documents, GPT 5.6 Luna, Gemini 3.1 Flash Lite and Gemini 3.5 Flash Lite.
GPT 6 Sol and Claude Opus 5.5 used the existing administrator access scope.
These eleven runs each uploaded two synthetic books through the UI, called
composition, attached a native file, and passed downloaded-file checks of every
value and all four live formulas, including cross-sheet relocation.
See [model matrix](artifacts/officecli-large-files/model-matrix.json).

GPT 6 Luna continued a native clone of the original 29-file chat, from its older
conversation branch before the historical multi-megabyte inspection dump.
Its first request omitted one source (28/29). The server returned an explicit
`source_set_incomplete` error; the model corrected its next request to all 29.
The downloaded 20.5 MiB result independently passed the full source comparison:
72361 nonempty cells and caches, 19435 formulas, 4517 merges and 37 image hashes.
Original files and the original chat were unchanged.

The first result did **not** satisfy chronological tab order: the model appended
the missing month at the end. A follow-up native move also used the wrong
zero-based index. Do not describe these attempts as successful ordering. The
composition contract follows the explicit source list; the model owns semantic
planning, and complete data preservation does not prove correct requested order.
Recomposition from the original 29 sources with an explicit month sequence
subsequently passed both chronological-order and full downloaded-file comparison.
The natural-language phrase "chronological order" alone is not a deterministic
sort guarantee; the server faithfully follows the explicit list sent by the model.

That follow-up exposed a separate completeness bug: the nearest generated
assistant artifact was mistaken for a new input set. Commit `04f940c4` makes
composition completeness follow the nearest **user upload on the active branch**.
The existing single-file edit resolver still selects the nearest result. Tests
cover an intervening generated attachment, a new replacement upload and a sibling
branch. This change does not modify composition, verification, CLI, Function,
provider transport or access grants.

The flight recorder sampled the primary container thirty times during the heavy
run: peak 3436871680 bytes (3.20 GiB), same container ID, restart count unchanged
at one, no OOM flag. Sidecar sample peak was 319492096 bytes (305 MiB), restart
count zero. These observations do not establish the cause of the earlier OOM
reported in issue #527. Aggregate [heavy-case evidence](artifacts/officecli-large-files/heavy29.json)
contains no source file IDs or financial contents.

The ordinary user received HTTP 404 for the administrator's new heavy artifact.
The two-file attachment survived page reload; switching GPT 5.4 Mini to Claude
Sonnet 4.6 in the same chat produced another verified composition without
re-uploading sources. See [continuation evidence](artifacts/officecli-large-files/continuation.json).

## Validation and release

Completed on image `sha256:405a0a5fa0cf284010dc0d97d3f61cb31f699eef8a0999f3026777d68d9c942e`:
150 tests, full source/result comparison, negative formula/value mutation checks,
authentication and failure cleanup, real OfficeCLI 66/256-command atomic batches,
and native DOCX/XLSX/PPTX create/batch/validate/content regression. The runtime
imports come from the installed image, with only test files mounted externally.

Final image `sha256:cb1364c31d6e170a8200f7a2b976833e41ca70b8ee821c29f0d6e565bc3fa80b`
contains implementation `04f940c4212c4841962725ce77cdbe3fc01d2291`.
All 152 tests passed against its installed modules; all eight live module hashes
match the archived source. Only `app.py` and `openwebui_client.py` differ from
the twelve-model composition baseline. Required CI runs
[36269603518](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/36269603518)
and [36272812192](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/36272812192)
passed before their respective deployments.

Sidecar container `3c50363af2ff` runs the final image; main container
`0fb174020e2d` remains healthy with restart count one. The native Function is
`1.1.0-large-workbooks`, LF SHA-256
`8f727e12d5f536fa6b305443de7be22031ed01de0637446b4c2ab8bc6b8ff04d`.
Active, Global, all twelve model targets, reasoning valves and access grants
are unchanged. The Tool Server schema was refreshed through the native config
route, without changing its configuration.

Deployment source, module hashes and rollback are recorded under
`/opt/officecli-openapi-proof-533-04f940c4`. The original pre-PR sidecar image and
Function backup remain available. The canonical procedure is in the
[OfficeCLI runbook](../../infra-ops/officecli-openapi-docx-release.md).

On the final installed image, an ordinary GPT 5.4 Mini chat completed both its
first composition and a follow-up from the same two source uploads with
`require_all_attachments=true`, one successful call each, no error and no
re-upload. Both downloaded outputs passed value/formula/dependency checks.
See [final follow-up evidence](artifacts/officecli-large-files/final-followup.json)
and [release identity](artifacts/officecli-large-files/release.json).

Cleanup removed the temporary ordinary user and its 32 files, two administrative
synthetic chats and six files, the isolated R&D container and experimental image
tag, and local/server source and output copies. Only aggregate public evidence
and minimal root-only receipts remain. Synthetic chat/file IDs in the matrix are
historical receipts; their temporary objects have been deleted. The original
29-source chat still has its original nineteen messages and current branch;
all twenty-nine source byte hashes remain unchanged. The delivery copy and its
native output attachments are retained. Recorder history, incidents and rollback
images are retained under their existing policies. The original dirty worktree
still has its twenty-one unrelated tracked changes and original HEAD.

The current GitHub authorization cannot update workflow files (`workflow` scope
missing). The existing required workflow is unchanged. Reproduce the additional
installed-image checks by mounting `services/officecli-openapi-proof/tests` at
`/qa` and `deploy/openwebui-functions` at `/functions`, then running:

```sh
python -m pytest -q /qa /functions/tests/test_officecli_auto_attach_filter.py
python /qa/verify_xlsx_large_batch.py
```
