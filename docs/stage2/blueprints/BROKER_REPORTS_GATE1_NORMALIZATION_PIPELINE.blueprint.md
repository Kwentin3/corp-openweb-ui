# Broker Reports Gate 1 Normalization Pipeline Blueprint

Status: GATE1_NORMALIZATION_PIPELINE_BLUEPRINT_READY
Date: 2026-07-07
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 "Document Intake & Normalization"

## 1. Executive Decision

Gate 1 is a technical and structural normalization pipeline.

It is not a tax parser, source-fact extractor, declaration generator, XLS/XLSX exporter, OCR batch processor, or FNS filing path.

The accepted product entrypoint is:

```text
OpenWebUI Workspace Model
-> base model = Pipe Function broker_reports_gate1_pipe
-> user attaches files in the same chat request
-> user asks for Gate 1 normalization
-> Pipe receives file refs
-> Gate 1 pipeline reads bytes under the approved boundary
-> private artifacts plus safe artifacts are created
-> safe Gate 1 report is returned to chat
```

The native Action/button path stays as a debug or secondary proof path. The DOM/static loader path is not the primary product path for this gate.

## 2. Problem And Risk

The current Pipe proof confirms same-request file-ref visibility, but it is still a stub. It returns safe counts from refs and does not yet prove original-byte hashing, parser-backed format profiling, bounded private slices, taxonomy candidate generation, or contract validation.

The main risk is mixing two different jobs:

- Gate 1: build a clean, safe, traceable map of the document package.
- Gate 2 and later: extract source facts, normalize tax events, prepare ledgers and declaration-oriented outputs.

If Gate 1 starts reading for tax facts, it will lose the audit boundary that makes later extraction reviewable.

## 3. Ownership Map

| Area | Owner | Responsibilities |
| --- | --- | --- |
| OpenWebUI Workspace Model | OpenWebUI workspace config | User-facing model name, instructions, primary UX route, chat report delivery. |
| Pipe Function | Gate 1 OpenWebUI function | Collect same-request file refs, call normalization run, return safe report. |
| OpenWebUI file layer | OpenWebUI runtime | Uploaded file ids, access control, original bytes or upload storage boundary. |
| Gate 1 normalizer | Internal helper/service module | Byte access, hashing, container detection, format profiling, private slices, taxonomy candidates, blockers. |
| Artifact store | Internal/private + safe docs surfaces | Private registries and slices stay private; safe artifacts can be cited by id. |
| Contract validator | Gate 1 validation module/tests | Enforce schema, privacy, blocker, and chat-visible report invariants. |
| Gate 2 consumer | Future source-fact extraction pipeline | Consumes safe document refs and private slice refs only after Gate 1 validation passes. |

## 4. Non-Goals

Gate 1 must not perform:

- NDFL or other tax calculation;
- source-fact extraction;
- declaration generation;
- XLS/XLSX export;
- FNS filing;
- mass OCR;
- LLM reading of all raw documents as one context;
- automatic Knowledge loading of customer source documents;
- separate user-facing sidecar UI;
- printing of raw filenames, file ids, private paths, account numbers, personal identifiers, full financial rows, raw parser text, secrets, or env values in chat-visible output.

## 5. Pipeline Stages

| Step | Goal | Input | Output | Preferred tool | Fail-closed behavior | Private data | Safe/chat-visible data | Required checks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Intake request | Confirm the Pipe received a request with file refs. | Chat body, messages, metadata, `__files__`. | `normalization_run_v0` started or `no_files` blocker. | Existing Pipe collection logic. | If no refs, return safe blocker report. | User prompt text, raw message structure, raw file ids. | `files_total=0`, blocker count, next step. | No prompt text or file ids in report. |
| 2. Private file registry | Preserve original refs without leaking them. | File refs from Pipe. | Private file registry entries. | Pydantic/dataclass model plus private store. | If registry cannot be created, stop before parsing. | File ids, original names, upload paths, original MIME metadata. | Safe `document_id`, counts. | Raw names and file ids never appear in chat. |
| 3. Byte access and hashing | Prove original bytes are accessible and stable. | Private file registry. | SHA-256, size, duplicate groups. | `hashlib`; approved OpenWebUI file API/storage boundary. | `bytes_unavailable` blocker per affected file. | Byte stream, upload path, raw filename. | Size, sha256 or sha256 prefix only where allowed, duplicate count. | Stable hash on repeat; no path escape. |
| 4. Container and MIME detection | Classify file container before parsing. | Bytes, MIME, extension. | `container_format`, detected MIME, confidence. | Magic bytes + extension + MIME; optional `filetype`/`python-magic`. | `unknown_format` or `unsupported_format` blocker. | Raw extension/name only in private registry. | Container counts. | Extension/MIME disagreements recorded. |
| 5. Format-specific profiling | Build technical readability profile. | Container-specific bytes. | `technical_readability_profile_v0`. | Format parsers listed in tooling audit. | `parser_failed`, `encrypted_file`, `corrupt_file`, or `raster_requires_ocr_or_review`. | Parser diagnostics, raw extracted text, raw rows/cells. | Counts and safe capability flags. | Profiles exist for every supported readable file. |
| 6. Structural normalization | Create bounded slices for later gates. | Parser outputs. | Private `normalized_text_slice_v0` and `normalized_table_slice_v0`. | Parser-backed text/table extraction. | Skip slices and create blocker when structure is unreliable. | Text slices, table rows, source locations, row ranges. | Slice counts and safe refs only. | Slices are bounded and source-located. |
| 7. Taxonomy candidates | Assign document role candidates without tax extraction. | Inventory, profile, safe structural signals. | `taxonomy_candidates_v0`. | Deterministic/rule-assisted classifier. | `unknown_role` blocker if weak. | Optional private reason evidence. | Class label, confidence, safe reason codes. | LLM is not authoritative in Gate 1. |
| 8. Blockers and review issues | Make unresolved technical problems explicit. | All prior artifacts. | `normalization_blockers_v0`. | Rule validator. | Block advancement to Gate 2 for affected documents. | Private debug context. | Blocker code, safe document id, action. | Every failure maps to typed blocker. |
| 9. Safe chat report | Return only safe aggregate status. | Validated safe artifacts. | `chat_visible_normalization_report_v0`. | Report renderer. | If privacy validation fails, do not publish report. | None. | Counts, class counts, case groups, blocker counts, next step, safety statement. | Privacy denylist and schema checks pass. |
| 10. Gate 2 handoff | Expose only approved refs to extraction. | Validated Gate 1 artifact refs. | Gate 2 input pack. | Contract mapping. | Gate 2 stays blocked until Gate 1 is valid. | Private slice refs under access control. | Safe document refs and readiness labels. | No source facts created by Gate 1. |

## 6. Operation Order

```text
collect_file_refs()
-> create_normalization_run()
-> create_private_file_registry()
-> read_original_bytes()
-> compute_sha256_and_size()
-> detect_container()
-> profile_by_format()
-> create_private_slices()
-> assign_taxonomy_candidates()
-> create_blockers()
-> validate_artifacts()
-> render_safe_chat_report()
-> prepare_gate2_handoff_refs()
```

No later step can compensate for a missing earlier safety check. For example, taxonomy cannot run on a file whose byte access failed, and Gate 2 cannot start from an unvalidated chat report.

## 7. Format Profiling Rules

### CSV and TXT

Collect:

- encoding and confidence;
- delimiter candidate;
- row count;
- column count;
- header candidate status;
- machine-readable table flag;
- bounded private text/table slices.

Preferred baseline: Python `csv`, text decoding, optional `charset-normalizer` or `chardet` after proof.

Do not use pandas in the first slice unless row volume or dialect handling proves the stdlib path insufficient.

### XLSX and XLS

Collect:

- workbook readability;
- sheet count;
- redacted or hashed sheet-name policy;
- hidden sheet count;
- formula presence;
- used ranges;
- table-like ranges;
- workbook role candidate.

Preferred baseline for XLSX: `openpyxl`.

XLS is separate from XLSX. If `xlrd` or a conversion path is not approved, emit `unsupported_format` or `parser_failed` instead of silently treating XLS as XLSX.

### PDF

Collect:

- page count;
- text-layer presence;
- raster/scan likelihood;
- table likelihood;
- page-level bounded text-slice refs;
- OCR-needed blocker.

Preferred candidates: `pypdf` for basic page/text proof or `PyMuPDF` for stronger text-layer/raster signals. `pdfplumber` is optional if table fidelity becomes a proof requirement.

Raster PDF does not trigger OCR in Gate 1. It creates `raster_requires_ocr_or_review`.

### HTML and TXT

Collect:

- clean text profile;
- table candidates;
- section labels;
- bounded slices.

Preferred baseline: stdlib `html.parser`/safe text extraction. Add BeautifulSoup only if the stdlib path is too brittle.

### DOCX

Collect:

- document readability;
- paragraph count;
- heading estimate;
- table count if available;
- document role candidate.

Preferred candidate: `python-docx`, but only as a Gate 1 dependency after proof. The STT sidecar currently declares `python-docx`; that does not by itself make it a Gate 1 runtime dependency.

### ZIP

Collect:

- member count;
- member extensions;
- size summary;
- nested archive flag;
- signature/XML/PDF markers if visible without recursive public unpacking.

Preferred baseline: stdlib `zipfile`.

ZIP members are not recursively unpacked into public artifacts. ZIP creates `zip_requires_review` unless a policy explicitly approves member extraction.

### Images

Collect:

- image container;
- size if available;
- OCR-needed blocker.

Image OCR is out of scope for Gate 1 implementation Slice 1. External OCR/VLM providers require separate data-policy approval.

## 8. Artifact Outputs

Gate 1 creates these artifact contracts:

- `normalization_run_v0`;
- `document_inventory_v0`;
- `technical_readability_profile_v0`;
- `normalized_text_slice_v0`;
- `normalized_table_slice_v0`;
- `zip_member_inventory_v0`;
- `taxonomy_candidates_v0`;
- `normalization_blockers_v0`;
- `chat_visible_normalization_report_v0`.

Private by default:

- file registry;
- original file ids;
- raw filenames;
- upload/local paths;
- parser diagnostics;
- raw text;
- raw rows/cells;
- normalized text/table slices.

Safe by default:

- generated run id;
- safe document ids;
- container counts;
- class counts;
- blocker counts;
- case group ids;
- readiness labels;
- next-step recommendation;
- explicit safety statement.

## 9. Blocker Codes

Minimum blocker set:

- `no_files`;
- `bytes_unavailable`;
- `unsupported_format`;
- `encrypted_file`;
- `corrupt_file`;
- `parser_failed`;
- `raster_requires_ocr_or_review`;
- `zip_requires_review`;
- `unknown_role`;
- `privacy_violation`;
- `duplicate_review`.

Blockers are contract artifacts, not prose-only warnings.

## 10. LLM Boundary

LLM is not the primary Gate 1 classifier and must not read all raw documents as one context.

Allowed in Gate 1 only after deterministic slicing and privacy review:

- suggest non-authoritative taxonomy alternatives;
- summarize safe aggregate status;
- draft operator next-step wording from safe artifacts.

Forbidden in Gate 1:

- extracting source facts;
- resolving tax meaning;
- deciding tax-base treatment;
- filling declaration fields;
- reading raw customer files as unbounded prompt context;
- overriding parser/validator blockers.

## 11. Validation Plan

Minimum checks:

- no-file request fails closed with `no_files`;
- file refs collected from same user request through Pipe;
- raw filenames, file ids, prompt text and private paths absent from chat output;
- byte hashes stable across repeated runs;
- duplicate content produces duplicate review signal;
- CSV/TXT profile records encoding, delimiter, rows and columns;
- XLSX profile records sheets, formulas, hidden sheets and used ranges;
- PDF profile records pages, text-layer and raster likelihood;
- raster PDFs create OCR/review blockers;
- ZIP creates member inventory plus review blocker;
- corrupt/unsupported files create blockers;
- every private slice has source location;
- chat-visible report contains only whitelisted fields;
- Gate 2 handoff is blocked until validation passes.

## 12. Implementation Slices

Implementation should proceed in these slices:

1. Pipe receives files and creates inventory/hash/container counts.
2. CSV/TXT profiling and private slices.
3. XLSX profiling.
4. PDF profiling.
5. ZIP inventory and blockers.
6. Taxonomy candidates.
7. Safe report and validation rules.

Each slice must leave the system in a runnable, fail-closed state.

## 13. Deferred Work

Deferred to Gate 2 or later:

- source-fact extraction;
- table-to-tax-event mapping;
- currency rate lookup;
- withholding interpretation;
- customer methodology resolution;
- ledgers;
- declaration model population;
- XLS/XLSX export;
- OCR/VLM provider integration;
- Knowledge population policy for customer samples.

## 14. Status

```text
GATE1_NORMALIZATION_PIPELINE_BLUEPRINT_READY
GATE1_TECHNICAL_STRUCTURAL_NORMALIZATION_CONFIRMED
PIPE_PRIMARY_ENTRYPOINT_CONFIRMED
LLM_SOURCE_FACT_EXTRACTION_DEFERRED_TO_GATE2
READY_FOR_GATE1_IMPLEMENTATION_SLICE_1
```
