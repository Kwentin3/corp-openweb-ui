# OpenWebUI Broker Reports Workspace And Gate 1 Runtime Proof Report

Date: 2026-07-06

Status: WORKSPACE_RUNTIME_PROOF_PARTIAL

Scope: Stage 2 Broker Reports / XLS NDFL Workspace Runtime Proof + Gate 1 Stub Proof

Operator action required: yes

If yes: see
`docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_WORKSPACE_GATE1_OPERATOR_HANDOFF.md`.

## 1. What Was Checked

This proof checked the minimum path needed before building the real Gate 1
normalizer:

```text
OpenWebUI scenario shell
-> client chat / uploaded file refs
-> explicit Normalize Documents trigger
-> proof-only Action/helper stub
-> safe chat-visible report
```

The live OpenWebUI runtime was not available locally during this run. Therefore
the report separates:

- previous runtime evidence from existing Stage 2 reports;
- current local runtime availability checks;
- current proof-only Broker Reports Action stub behavior;
- remaining operator steps for a real OpenWebUI UI/API run.

No customer documents were used.

## 2. OpenWebUI Runtime Version

Current live runtime version was not re-proven in this run.

Current local checks:

```text
docker ps: no openwebui/stage2 containers running
GET http://127.0.0.1:8080/api/config: unreachable
GET http://127.0.0.1/api/config: unreachable
GET https://127.0.0.1/api/config: unreachable
```

Reusable previous evidence:

- `docs/reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md`
  recorded OpenWebUI `0.9.6` via unauthenticated `/api/config` and
  `/api/version`.
- `compose/openwebui.compose.yml` still targets OpenWebUI `v0.9.6` by default.

This is not treated as a fresh live-version proof.

## 3. Workspace Model Proof

Current run:

- the Broker Reports Workspace Model was not created or modified in a live
  OpenWebUI runtime;
- no OpenWebUI production/staging configuration was changed;
- no Knowledge, Prompt, Skill, Tool or Action was populated in OpenWebUI.

Reusable previous Stage 2 proof:

- a synthetic group-restricted Workspace Model named `Stage2 Proof Scenario`
  was created and then cleaned up in the 2026-06-24 actor proof;
- inside user visibility was true;
- outside user visibility was false;
- group preview/access endpoints were proven for the synthetic group.

Broker Reports-specific runtime model remains operator-gated.

## 4. Group Visibility

Current Broker Reports group visibility was not live-tested.

The accepted target remains:

```text
Broker Reports / XLS NDFL Draft Scenario
-> visible only to the approved Broker Reports group
-> hidden from outside users
```

The previous four-actor proof is enough to keep the native Workspace Model route
plausible, but not enough to claim this Broker Reports scenario exists today.

## 5. Prompts, Skills And Knowledge

Current run:

- no Prompt was created;
- no Skill was created;
- no Knowledge collection was created;
- no customer document was added to Knowledge.

Configuration proposal status:

- Prompt candidate: `/broker_gate1_normalize`;
- Skill candidates: safety discipline and Gate 1 workflow discipline;
- Knowledge boundary: approved methodology/reference docs only;
- customer uploads remain chat files, not Knowledge.

## 6. Trigger Path Checked

Trigger priority from the Stage 2 docs remains:

1. Action.
2. Workspace Tool.
3. OpenAPI Tool Server / helper.
4. Slash prompt fallback.

Current run implemented and tested a proof-only Action stub:

```text
services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_normalizer_action.py
```

The stub is not a production normalizer. It only proves safe collection and
projection behavior for expected OpenWebUI Action file-ref shapes.

Previous STT runtime evidence matters here:

- the live OpenWebUI Action endpoint passed file refs through `body["files"]`;
- `__metadata__` and `__files__` were not passed separately by that endpoint in
  the STT Action proof;
- Action API returned content through the OpenWebUI Action response.

Current Broker Reports live Action install/run was not performed.

## 7. Can Trigger See Uploaded File Refs?

Stub/unit boundary:

```text
FILE_REFS_VISIBLE_TO_TRIGGER
```

The proof-only Action stub accepts:

- `body["files"]`;
- `__metadata__["files"]`;
- `__files__`.

The tests confirmed that all three expected shapes are normalized into safe
document summaries without exposing raw filenames or file ids in chat content.

Live Broker Reports runtime boundary:

```text
FILE_REFS_NOT_VISIBLE_TO_TRIGGER
```

Reason: no live OpenWebUI Broker Reports Action was installed or executed in
this run.

## 8. Can Helper/Stub Get Original Bytes?

Stub/unit boundary:

```text
ORIGINAL_BYTES_ACCESS_PROVEN
```

The proof-only Action stub can read bytes from a configured upload root using
the same guarded upload-root pattern as the Stage 2 STT Action:

```text
upload_root / "{file_id}_{filename}"
```

The test uses a temporary synthetic upload root and proves:

- bytes can be read under the approved root;
- path escape is blocked by `Path.resolve()` and parent checking;
- raw CSV rows are not published to chat content.

Live Broker Reports runtime boundary:

```text
ORIGINAL_BYTES_ACCESS_BLOCKED
```

Reason: no live OpenWebUI upload file was available to the Broker Reports stub.

## 9. Same-Chat Safe Report

Stub/unit boundary:

The proof-only Action returns:

- `content`: chat-visible markdown with a JSON safe report;
- `broker_reports_gate1_report`: structured report object.

The chat-visible content includes:

```text
Next step: Select case_group_synthetic_001
```

Live Broker Reports runtime boundary:

```text
SAME_CHAT_SAFE_REPORT_BLOCKED
```

Reason: no live OpenWebUI Action/UI run was available in this environment.

## 10. Privacy Violations

No privacy violation was found in the new proof artifacts.

Controls applied:

- only synthetic files were created;
- no customer documents were read;
- `.env` values were not read or printed;
- no provider/admin token was printed;
- no raw local customer path was printed;
- chat-visible stub output omits raw filenames, raw file ids and full table rows;
- tests assert that raw synthetic CSV row content is not published.

## 11. What Worked

Created proof-only Broker Reports stub:

- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_normalizer_action.py`

Created focused tests:

- `services/broker-reports-gate1-proof/tests/test_broker_reports_gate1_action_stub.py`

Created synthetic fixtures:

- `docs/stage2/testdata/broker_reports_gate1_stub/README.md`
- `docs/stage2/testdata/broker_reports_gate1_stub/synthetic_gate1_text_pdf_or_txt.txt`
- `docs/stage2/testdata/broker_reports_gate1_stub/synthetic_gate1_operations.csv`

Validated behavior:

```text
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
-> Ran 4 tests in 0.009s
-> OK

python -m compileall services/broker-reports-gate1-proof
-> passed
```

The tests assert observable Action return behavior:

- safe report schema;
- file counts;
- container counts;
- safe case group;
- no raw filename in content;
- no raw file id in content;
- no raw synthetic account marker in content;
- bytes access under temporary upload root;
- fail-closed no-file-refs response.

## 12. What Did Not Work

The live OpenWebUI proof did not run because no local OpenWebUI runtime was
available:

```text
docker ps: no openwebui containers running
localhost OpenWebUI API: unreachable
```

The agent did not read `.env` or recover admin credentials, so it could not
authenticate to a remote or stopped runtime.

No real Broker Reports Workspace Model was created.

No real Broker Reports Action was installed.

No real OpenWebUI chat upload was performed.

No same-chat visual UI proof was captured.

## 13. Blockers

Primary blockers:

1. No running local OpenWebUI container.
2. No approved live runtime session for this proof.
3. No approved way in this run to read or use admin credentials.
4. Broker Reports Action is not installed in OpenWebUI.
5. Broker Reports Workspace Model is not created in the current runtime.

Non-blockers:

- lack of customer documents, because this proof must use synthetic files only;
- lack of OCR, because OCR is outside this proof;
- lack of production parser, because this proof intentionally stops at stub.

## 14. Operator Handoff

Operator action required: yes

Exact minimal steps are in:

```text
docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_WORKSPACE_GATE1_OPERATOR_HANDOFF.md
```

The handoff asks the operator only to:

- start/open OpenWebUI;
- create or verify a restricted Broker Reports Workspace Model;
- install the proof-only Action;
- upload synthetic files;
- call the Action;
- confirm whether `body["files"]` reaches the Action and whether same-chat
  content appears.

## 15. Recommendation

Choose Action as the next trigger path.

Reason:

- previous STT proof already showed OpenWebUI Action API can receive
  `body["files"]`;
- the new Broker Reports stub is compatible with that proven shape;
- the Action can return safe chat content and structured payload;
- the helper can later be moved behind an OpenAPI/internal sidecar boundary
  without changing the user-facing OpenWebUI workflow.

Do not choose slash prompt as the primary path. It is acceptable only as a
fallback command that delegates to the Action/Tool.

If the native Action UI is not discoverable enough, reuse the Stage 2 extension
order:

```text
Action API
-> optional thin static loader/control
-> private helper sidecar
```

No separate user-facing sidecar UI is recommended.

## 16. Final Statuses

Runtime statuses:

```text
WORKSPACE_RUNTIME_PROOF_PARTIAL
GATE1_TRIGGER_NOT_PROVEN
FILE_REFS_NOT_VISIBLE_TO_TRIGGER
ORIGINAL_BYTES_ACCESS_BLOCKED
SAME_CHAT_SAFE_REPORT_BLOCKED
READY_FOR_TRIGGER_PATH_DECISION
OPERATOR_ACTION_REQUIRED
```

Local proof-only stub statuses:

```text
FILE_REFS_VISIBLE_TO_TRIGGER
ORIGINAL_BYTES_ACCESS_PROVEN
READY_FOR_GATE1_NORMALIZER_STUB_IMPLEMENTATION
```

These statuses intentionally distinguish current live OpenWebUI evidence from
local proof-only stub evidence.
