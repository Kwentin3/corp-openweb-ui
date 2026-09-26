# OfficeCLI: all published model profiles

Qualification checkpoint: 2026-09-26. Scope is the eight models selected by the
OfficeCLI Auto Attach filter and the existing Office Documents workspace profile.
No unrelated workspace/Pipe models are included.

| Published ID | Downloaded XLSX product test | Candidate native protocol replay |
| --- | --- | --- |
| claude-sonnet-4-6 | PASS, prior product report | unchanged |
| gpt-5.4-mini | PASS, prior product report | unchanged |
| gpt-5.6-luna | PASS, prior product report | unchanged |
| claude-opus-5 | PASS, fresh ordinary UI chat | unchanged |
| office-documents | PASS, fresh ordinary UI chat after upload capability repair | unchanged |
| models/gemini-3.5-flash | NOT RUN on candidate image | PASS, real signed provider round trip |
| models/gemini-3.6-flash | NOT RUN on candidate image | PASS, real signed provider round trip |
| models/gemini-3.1-flash-lite | NOT RUN on candidate image | PASS, real signed provider round trip |
| models/gemini-3.5-flash-lite | NOT RUN on candidate image | PASS, real signed provider round trip |

Product checks upload jan.xlsx and feb.xlsx through the ordinary chat UI, inspect
both exact native attachment IDs, create a native result attachment, download it,
and compare every source cell, formula, sheet name and topology. Expected totals
are 350 and 550; exactly two sheets and four rows per sheet are required. The
Opus and Office Documents result binaries are retained in artifacts below.
Earlier evidence and fixture verification live in
[the primary product report](OFFICECLI_MULTI_XLSX_PRODUCT.report.md).

Office Documents previously had `meta.capabilities.file_upload=false`. Its first
chat therefore contained no user file references. Changing that existing flag to
true and explicitly including `office-documents` in the filter target/native
lists repaired the observed route. Its base model, grants and tool IDs remain
owned by the existing workspace profile.

Opus passing chat: `7d17757b-0ce4-4df8-912f-357078ac315f`;
result `fb562a8e-d39b-4758-aa4a-864714e79e51`.
Office Documents passing chat: `db45aefa-79a8-4450-b47f-0d9741edd02c`;
result `998c7f4d-35cc-4ffe-a1c1-9dd373a41df8`.
Both downloads returned HTTP 200 and passed the existing strict workbook verifier.

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

Candidate image: `corp-openwebui/openwebui:officecli-all-models-candidate-20260926`.
Image ID: `sha256:f715c1e64a9818fd79778772634ddf9e5b329cd51d8759001ff80b9dfb717772`.
It derives from the exact currently deployed media image, preserving the earlier
media overlays. Its build runs the replay against the installed native functions;
an isolated `--network none` container repeats that verification.

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
The production main container and OfficeCLI sidecar have not been restarted.

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
The temporary probe was removed and the native model list restored to the five
already qualified profiles while the corrected candidate is prepared.

Activation requires the separate agreement explicitly required by
[the release runbook](../../infra-ops/officecli-openapi-docx-release.md).
After approval and required CI, update only the main image through its existing
deployment owner, verify the image/receipt, then qualify all nine profiles through
ordinary user chats. Include a Gemini follow-up without re-upload and model switch.
Do not mark Gemini product acceptance complete from this protocol replay.

Rollback image: `corp-openwebui/openwebui:media-intake-audio-release-20260925`,
ID `sha256:114f20df22d1e4f33e9381a5e75492db92310b98f61694e6f7e5f1c1c5336a6b`.
Rollback also restores the five-model native list; the Office upload repair remains
independently verified. No volumes, chat data or sidecar changes are needed.
Remove this adaptation when native provider/runtime compatibility is verified;
new runtime hashes require explicit requalification.
