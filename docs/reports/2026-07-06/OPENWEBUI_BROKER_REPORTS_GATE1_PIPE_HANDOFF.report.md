# OpenWebUI Broker Reports Gate 1 Pipe Handoff Report

Date: 2026-07-06
Repository: corp-openweb-ui
Scope: Stage 2 epic Broker Reports / XLS NDFL, Gate 1 Document Intake & Normalization proof workflow.

## 1. Executive Summary

The working Gate 1 launch path is now proven through an OpenWebUI Pipe Function used as the base model for a Workspace Model.

The successful user workflow is:

```text
Workspace Model
  -> base model = Pipe Function "NDFL. Broker Reports / Gate 1"
  -> user attaches source documents
  -> user sends "нормализуй" or "Нормализация Gate 1"
  -> Pipe receives file refs from the same chat request
  -> Pipe returns a safe Gate 1 report directly in chat
```

This replaces the earlier Action-button direction for Gate 1. The Action remains useful as a debug/proof endpoint, but it is not the recommended product trigger for document intake.

## 2. Proven Runtime Result

The user manually tested the Workspace Model wrapper over the Pipe base model. The chat returned immediately with:

```json
{
  "file_ref_visibility": "visible",
  "summary_counts": {
    "files_total": 2,
    "container_counts": {
      "csv": 1,
      "txt": 1
    },
    "blockers_total": 0
  },
  "trigger_type": "pipe_stub"
}
```

This proves that files attached to the same user message are visible to the Pipe path.

Safe-boundary confirmation:

- no tax calculation was performed;
- no declaration was generated;
- no XLS/XLSX export was generated;
- no source-fact extraction through LLM was performed;
- the report did not include raw filenames, file ids, customer file contents, or operation rows.

## 3. Why Action/Button Was Not the Right Main Path

The first proof used an OpenWebUI Action Function:

```text
broker_reports_gate1_normalizer_action
```

Direct API calls to the Action worked when the request body explicitly contained `files`.

The native OpenWebUI Action button did not work for this workflow because it runs under an assistant message context. The documents are attached to the user message/composer turn. In that native Action context, uploaded file refs were not reliably available and the Action returned:

```text
No uploaded file refs were visible.
```

A custom static-loader button was also explored by analogy with the existing STT loader. This is technically possible but not recommended as the Gate 1 product path because it depends on unstable UI details:

- DOM shape of attachment chips;
- truncated visible filenames;
- upload response timing;
- loader cache and refresh timing;
- OpenWebUI frontend changes between versions.

Conclusion: the custom composer/button path is a brittle workaround. Do not continue it as the primary Gate 1 workflow unless a specific shortcut is explicitly required later.

## 4. Working Architecture

There are now two different OpenWebUI concepts involved.

### 4.1 Pipe Function

Installed Function id:

```text
broker_reports_gate1_pipe
```

Function type:

```text
pipe
```

Current display name after encoding fix:

```text
НДФЛ. Брокерские отчеты / Gate 1
```

Implementation file:

```text
services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py
```

Purpose:

- backend proof engine;
- receives chat request and uploaded file refs;
- returns safe Gate 1 report directly as model output;
- currently returns `pipe_stub` report, not full document normalization.

### 4.2 Workspace Model Wrapper

The user proved that a Workspace Model can use the Pipe Function as its base model.

Manual proof performed by user:

```text
Create Workspace Model named "test"
Select base model = НДФЛ. Брокерские отчеты / Gate 1
Create new chat
Select Workspace Model "test"
Attach file
Send prompt "нормализуй"
Receive normalization report immediately
```

This is the preferred UX pattern:

```text
Workspace Model = user-facing product surface
Pipe Function = backend Gate 1 engine
```

Recommended final naming to avoid confusion:

```text
Backend Pipe Function:
  Broker Reports Gate 1 Pipe Engine

Workspace Model:
  НДФЛ. Брокерские отчеты / Gate 1
```

The exact final names can be chosen later, but the split should stay explicit.

## 5. Encoding Incident and Fix

During one admin API update, the Russian display name was sent through a Windows PowerShell path that corrupted Cyrillic into question marks:

```text
question-mark mojibake string ending with / Gate 1
```

Fix applied:

- resent the display name using Python Unicode escape literals;
- verified by reading back the model/function name as Unicode escapes;
- confirmed `question_marks_left = False`.

Future rule:

- when updating Russian names through scripts, avoid raw Cyrillic through ambiguous PowerShell stdin;
- prefer UTF-8 files or Python strings using `\u` escapes;
- verify with `name.encode("unicode_escape")` or equivalent.

## 6. Local Files Added or Changed

Primary proof files:

```text
services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py
services/broker-reports-gate1-proof/tests/test_broker_reports_gate1_pipe_stub.py
```

Earlier Action proof files still present:

```text
services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_normalizer_action.py
services/broker-reports-gate1-proof/tests/test_broker_reports_gate1_action_stub.py
```

Experimental static loader changes exist but should not be treated as the primary Gate 1 path:

```text
deploy/openwebui-static/loader.js
services/stage2-stt/tests/test_loader_static.py
```

## 7. Validation Performed

Local test command:

```text
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
```

Result:

```text
8 tests OK
```

Compile check:

```text
python -m compileall services/broker-reports-gate1-proof
```

Result:

```text
OK
```

Whitespace check:

```text
git diff --check
```

Result:

```text
OK for touched Gate 1 files
```

Runtime API smoke:

```text
upload two synthetic files through OpenWebUI Files API
send chat completion to broker_reports_gate1_pipe
receive report with file_ref_visibility=visible and files_total=2
delete synthetic uploads
```

Observed safe result:

```text
file_ref_visibility=visible
files_total=2
container_counts={'csv': 1, 'txt': 1}
privacy_ok=True
```

## 8. Current Limitations

The current Pipe is still proof-only.

It does not yet perform real Gate 1 normalization:

- no recursive package inventory;
- no sha256 calculation for original uploaded bytes;
- no PDF page/text/table profiling;
- no XLS/XLSX sheet/formula/hidden sheet profiling;
- no CSV delimiter/encoding/row profiling;
- no taxonomy classification beyond `unknown_or_needs_review`;
- no case grouping beyond the synthetic placeholder;
- no persistent safe registry artifact.

It also does not yet enforce a final product naming/access-control model. The user confirmed a Workspace Model wrapper can be created manually and can use the Pipe as base model.

## 9. Recommended Next Work

Recommended next engineering slice:

```text
Replace pipe_stub with real Gate 1 safe document intake.
```

Suggested implementation order:

1. Keep the Pipe as the product entrypoint.
2. Move shared Gate 1 report construction into a small service module so Action and Pipe do not duplicate logic.
3. Add safe file inventory fields:
   - document_id;
   - sanitized filename hash only, not raw filename in chat;
   - extension;
   - MIME/container type;
   - size;
   - sha256 when bytes are safely available;
   - readable/unreadable;
   - source context counts.
4. Add format-specific light profiling:
   - CSV/TXT encoding, delimiter, row/column summary;
   - XLS/XLSX sheet count and safe sheet names only when non-PII;
   - PDF page count, text layer/raster likelihood, table likelihood;
   - DOCX paragraph/headings estimate.
5. Add taxonomy candidate classification using the existing Stage 2 taxonomy docs.
6. Return only safe chat-visible report fields.
7. Optionally persist a private local registry artifact outside public chat output.

## 10. Suggested New-Chat Prompt

Use this to resume tomorrow:

```text
We are in the canonical repository worktree.
Continue Stage 2 Broker Reports / XLS NDFL Gate 1 work.
Read docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_GATE1_PIPE_HANDOFF.report.md first.
Current proven workflow: OpenWebUI Workspace Model uses base model Pipe Function `broker_reports_gate1_pipe`; user attaches files and sends `нормализуй`; Pipe receives file refs and returns safe Gate 1 report.
Do not continue the composer/button path as primary. Replace the current `pipe_stub` with real safe document intake/classification/technical profiling, without tax calculation, declaration generation, XLS export, OCR mass-processing, or PII leakage.
```

## 11. Bottom Line

The important product decision is now clear:

```text
Use Workspace Model for UX.
Use Pipe Function as Gate 1 backend engine.
Do not use Action button as the main document-intake trigger.
```

The proof has moved from "can we trigger code somehow" to "we have a contract-compatible OpenWebUI path and can now implement real Gate 1 intake".
