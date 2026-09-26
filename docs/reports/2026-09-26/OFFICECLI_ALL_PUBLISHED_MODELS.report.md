# OfficeCLI: all published model profiles

Final product qualification: 2026-09-26. All nine profiles PASS on deployed release
`officecli-all-models-release-20260926`, image
`sha256:095f1a356b38d2461265b58a8b9fbc6d97063b41d68712193a5c08c94bb04097`,
implementation `7176d602422adca2c6f3ea5014507b5d203a3755`.
The main image was updated after successful CI and explicit user approval.

[Final acceptance matrix](artifacts/officecli-all-models/acceptance.json) binds all
nine fresh ordinary-user chats to receipts, downloaded XLSX files and SHA-256.
Run `python docs/reports/2026-09-26/artifacts/officecli-all-models/verify_acceptance.py`.
It verifies original file IDs, owner, binary hashes and every extracted source
cell, successful RPC result ID matching the native output attachment, HTTP 200
download/metadata, and exact workbook values, formulas, cached totals and topology.
All nine pass: two sheets, four rows by four columns, totals 350 and 550.

Lightweight Gemini used native OpenWebUI's complete file context rather than
calling inspect again. Both documents are bound to the original uploaded IDs,
owner and fixture hashes; the prompt contained no source values or IDs. Gemini
3.1's first create failed after sheet rename left later paths at `/Sheet1`; it
corrected those paths autonomously and produced one successful result. Completed
tool-call status is not treated as RPC success. This qualification covers data
and formulas, not faithful copying of complex workbook styling/drawings.

The implementation CI [36231932753](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/36231932753)
passed. Focused suite was repeated against final source: 68 passed.
Main mounts, data volume, frontend/media bytes and native file/storage owners
were preserved; OfficeCLI sidecar was neither restarted nor changed.

Temporary acceptance state was removed: 44 files, 15 chats and the temporary
ordinary user; all deletes succeeded. The original admin session was restored
and seven task-created browser tabs closed. Server scratch was removed after
moving rollback backups to a root-only state directory. See
[cleanup receipt](artifacts/officecli-all-models/cleanup.json). Result binaries
and content-free proof remain in this PR. The original unrelated worktree is
preserved; the isolated PR worktree remains available for review.

Mini to Gemini 3.5 switching and a Gemini follow-up after a browser reload also
passed without re-uploading the original files. The saved history records the
actual selected model (reload restored Mini, then Gemini was explicitly selected).
[History receipt](artifacts/officecli-all-models/history-final.json) retains both
additional verified workbooks and original source IDs.

Both Filter model lists now contain all nine IDs in the acceptance matrix;
the no-reasoning exception contains only Luna. Office Documents' existing
file_upload capability is true; base model, grants and tool IDs are unchanged.

## Gemini cause and minimal image adaptation

Actual streamed responses from all four Gemini models omit tool-call index and
include `extra_content.google.thought_signature`. OpenWebUI 0.9.6 ignores calls
without an index and drops the Google field when recording/reconstructing native
function-call output. The public filter inlet is not invoked between native tool
rounds, so a filter alone cannot preserve this history representation.

The image overlay changes only the native parser/output representation in two
runtime files. It assigns indices only to complete identifiable Gemini calls and
deep-copies the original Google field through native output and history. It
does not invent signatures, bypass validation, cache provider state, replace the
tool loop or introduce a second provider client. Unknown source hashes fail
before writes; repeated application verifies the original receipt.

The installed original files exactly match upstream v0.9.6:

- middleware.py: `861978ea80b69c4201c0742d1401691834ea7202e75d4eb47250ac0c14af2ea9`
- misc.py: `636d5aa53907733def4999677f1720d5d0a900934c67d3e88f115584d2ba9db8`

The release derives from the existing media image, preserving its exact overlays.
Its build verifies the installed native functions.

Each real provider call was then reconstructed by those candidate-image native
functions and sent through the existing authenticated provider endpoint. All
four returned HTTP 200 and the correct sum 900. Removing only the original Google
field from the 3.5 Flash control returned HTTP 400. These are protocol checks,
not acceptance of the registered OfficeCLI/browser route. Opaque signatures and
credentials are excluded from committed evidence.

Relevant primary sources:
[OpenWebUI issue 28492](https://github.com/open-webui/open-webui/issues/28492),
[OpenWebUI discussion 19760](https://github.com/open-webui/open-webui/discussions/19760),
[Google thought signatures](https://ai.google.dev/gemini-api/docs/thought-signatures).

## Validation and activation boundary

Focused regression suite: 68 passed (15 filter, 46 OfficeCLI service, 7 protocol
adaptation tests). Native replay additionally covers parallel indices, persisted
history round trips, intact Google fields and unchanged existing OpenAI indices.
The main container is healthy on the release image; the sidecar is unchanged.

### First activation and scope regression

After successful CI and explicit user approval, the first candidate was activated
with preserved mounts. The first actual Gemini UI chat returned empty output.
A temporary content-free stream probe showed a complete signed `create_tasks`
call, so the provider had supplied a valid call. Inspection identified a Python
scope error in the overlay: the native `response_handler` assigns `model_id` in
its selected-model branch, making that name local and unbound on ordinary chunks.
The earlier extracted-loop verifier incorrectly supplied a `model_id` parameter
and concealed that binding.

The correction reads the existing `form_data` owner directly. The verifier now
retains the actual selected-model assignment in its scope; against the first
candidate it fails with the same `UnboundLocalError`. The corrected patch uses
marker V2 so an earlier V1 overlay is rejected rather than treated as qualified.
The temporary probe was removed. The corrected release was deployed after its
required CI passed and all nine profiles were then qualified through ordinary UI chats.

Separate restart approval was obtained under [the release runbook](../../infra-ops/officecli-openapi-docx-release.md).

Rollback image: `corp-openwebui/openwebui:media-intake-audio-release-20260925`,
ID `sha256:114f20df22d1e4f33e9381a5e75492db92310b98f61694e6f7e5f1c1c5336a6b`.
Rollback also restores the five-model native list; the Office upload repair remains
independently verified. No volumes, chat data or sidecar changes are needed.
Remove this adaptation when native provider/runtime compatibility is verified;
new runtime hashes require explicit requalification.
