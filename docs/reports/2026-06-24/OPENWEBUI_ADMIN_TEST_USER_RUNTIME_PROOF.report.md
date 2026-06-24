# OpenWebUI Admin/Test-User Runtime Proof

Date: 2026-06-24

Repository: `Kwentin3/corp-openweb-ui`

Scope: Stage 2 / PRD-1 native OpenWebUI capabilities, authenticated
Admin/Test-User four-actor runtime proof.

Verdict: `admin_test_user_runtime_proof_partial_with_actor_matrix`

## Executive Summary

The Admin/Test-User Runtime Proof was repeated with authorized admin
credentials from the local workspace `.env`. Credential values were not
printed, copied into documentation, committed, exported as cookies/tokens, or
stored in screenshots.

The previous credentials blocker is closed. The run authenticated as admin,
created temporary synthetic proof actors and resources, executed the four-actor
matrix, and then deleted all created proof entities. Cleanup verification found
no `stage2-proof-*` leftovers.

The proof is partial rather than passed because the deployed OpenWebUI runtime
showed four real product-policy gaps:

- native no-delete is not currently enforced: non-admin chat delete returned
  `200`;
- Web Search is globally enabled: both inside and outside synthetic employees
  could run the safe query;
- manager visibility through explicit shared-chat access did not appear in the
  manager shared list during the run, although personal/outside negative
  controls were blocked;
- native analytics completions succeeded, but admin analytics did not expose
  both synthetic users as rows during the same run.

These are not credentials blockers. Gate 7 is now backed by runtime actor
evidence and should remain partial only because of the concrete gaps above.

## Credential Handling

| Variable | Present |
| --- | --- |
| `WEBUI_ADMIN_EMAIL` | yes |
| `WEBUI_ADMIN_PASSWORD` | yes |

Additional runtime target variable:

| Variable | Present |
| --- | --- |
| `OPENWEBUI_HOST` | yes |

Credential values were not printed. No password, cookie, bearer token, session
token, browser storage dump, network trace or screenshot with secrets was saved.
The deployed URL is intentionally omitted from this report.

## Runtime Proof Run

Runtime version: OpenWebUI `0.9.6`

Proof run id: `20260624184721`

State-changing actions were limited to synthetic proof data approved by the
operator.

Created during the run:

- users: `stage2-proof-manager`, `stage2-proof-inside`,
  `stage2-proof-outside`;
- group: `Team-Stage2-Proof`;
- Workspace Model: `Stage2 Proof Scenario`;
- prompt: `/stage2_proof_summary`;
- Knowledge: `Stage2 Proof Knowledge`;
- files: synthetic TXT, PDF, DOCX-placeholder and XLSX-placeholder;
- chats: inside personal draft, inside shared work chat, outside analytics
  chat, delete probe chat.

Deleted during cleanup:

- all three synthetic users;
- `Team-Stage2-Proof`;
- `Stage2 Proof Scenario`;
- `/stage2_proof_summary`;
- `Stage2 Proof Knowledge`;
- all four synthetic files/placeholders;
- all created synthetic chats except the delete probe, which had already been
  deleted by the non-admin delete test.

Cleanup verification:

```text
leftovers: []
```

No production policy was changed. No real user rights were changed. No customer
documents or real personal data were used. No provider was connected. No
LiteLLM/gateway/deep fork work was started.

## Actors Used

| Actor | Runtime actor | Role / scope | Result |
| --- | --- | --- | --- |
| Admin | approved env admin account | OpenWebUI admin | authenticated; token not printed |
| Manager/PO | `stage2-proof-manager` | ordinary user, no admin role | created, tested, deleted |
| Employee inside group | `stage2-proof-inside` | ordinary user, member of `Team-Stage2-Proof` | created, tested, deleted |
| Employee outside group | `stage2-proof-outside` | ordinary user, no test group membership | created, tested, deleted |

The Manager/PO actor was not given admin role or blanket admin access.

## Runtime Setting Inventory

Confirmed non-secret runtime setting paths from authenticated `/api/config`:

```text
permissions.workspace.models=false
permissions.workspace.prompts=false
permissions.workspace.knowledge=false
permissions.features.web_search=true
permissions.chat.file_upload=true
permissions.chat.delete=true
permissions.chat.delete_message=true
permissions.chat.stt=true
```

Confirmed audio/STT config key names from authenticated `/api/v1/audio/config`
without values:

```text
stt_keys=ALLOWED_EXTENSIONS,AZURE_API_KEY,AZURE_BASE_URL,AZURE_LOCALES,AZURE_MAX_SPEAKERS,AZURE_REGION,DEEPGRAM_API_KEY,ENGINE,MISTRAL_API_BASE_URL,MISTRAL_API_KEY,MISTRAL_USE_CHAT_COMPLETIONS,MODEL,OPENAI_API_BASE_URL,OPENAI_API_KEY,SUPPORTED_CONTENT_TYPES,WHISPER_MODEL
tts_keys=API_KEY,AZURE_SPEECH_BASE_URL,AZURE_SPEECH_OUTPUT_FORMAT,AZURE_SPEECH_REGION,ENGINE,MISTRAL_API_BASE_URL,MISTRAL_API_KEY,MODEL,OPENAI_API_BASE_URL,OPENAI_API_KEY,OPENAI_PARAMS,SPLIT_ON,VOICE
```

Only key names were recorded. Provider credential values were not printed.

## Proof Matrix

| Domain | Check | Admin | Manager/PO | Employee inside group | Employee outside group | Result | Evidence | Gap | Recommendation |
| ------ | ----- | ----- | ---------- | --------------------- | ---------------------- | ------ | -------- | --- | -------------- |
| Groups / RBAC | Create group and verify Preview Access | created users/group and added inside user | not member | `inside_groups=1` | `outside_groups=0` | `passed` | group preview returned keys `group,knowledge,models,permissions,tools` | none for synthetic group membership | use real group matrix only after customer approval |
| Workspace Models | Group-restricted `Stage2 Proof Scenario` | created model over existing base model | not granted | `inside_sees=true` | `outside_sees=false` | `passed` | model list visibility differed by actor; base model id not printed | no UI screenshot proof | verify UI labels in operator session if screenshots are required |
| Shared Prompts | `/stage2_proof_summary` prompt and history | created prompt and grant | not granted | `inside_sees=true` | `outside_sees=false` | `passed` | prompt history endpoint confirmed | no browser slash-menu screenshot | keep prompt ownership/change policy as customer decision |
| Knowledge | Synthetic Knowledge access and retrieval | created Knowledge and added TXT file | not granted | `inside_sees=true`, retrieval `ok_200` | `outside_sees=false` | `passed` | file added to Knowledge; retrieval endpoint returned `200` | no customer document/OCR proof | use customer samples only after data policy approval |
| Analytics / usage | Two synthetic users and admin analytics | analytics endpoint reachable | ordinary user | completion `ok` | completion `ok` | `partial` | admin analytics returned `synthetic_rows=0` during run | no immediate per-user synthetic analytics rows | treat native analytics as basic visibility; consider export/gateway only after customer decision |
| Web Search permissions | Safe query with inside/outside actors | feature setting visible | not tested for manager | safe query `ok`, count `6` | safe query `ok`, count `6` | `partial` | `permissions.features.web_search=true`; raw results not saved | outside user can search because global default is enabled | customer must approve scoped rollout/default policy before claiming group-only Web Search |
| Chat deletion / no-delete | Non-admin API delete attempt | config visible | not admin | delete probe returned `200` | not needed | `failed-for-no-delete` | `permissions.chat.delete=true`; non-admin delete status `200` | no-delete is not enforced on current runtime | customer retention/no-delete decision or custom delete guard required |
| Manager visibility | Explicit shared work chat vs personal draft | grants configured | shared list did not show work chat | personal draft hidden from manager | shared link returned `401` for outside | `partial` | `share_id_created=true`, grant update `200`, manager personal status `401`, outside shared status `401`, manager shared list `false` | positive manager visibility not confirmed | do not use admin role as workaround; verify UI/shared resource semantics before rollout |
| Synthetic file upload | TXT/PDF/DOCX/XLSX upload | not required | not required | uploaded all four | not granted | `passed-partial-extraction` | TXT and PDF uploaded with processing; DOCX/XLSX placeholders uploaded without processing | valid DOCX/XLSX parsing and extraction quality not proven | keep OCR/XLSX/customer document quality outside this proof |
| Native STT settings inventory | Audio config key inventory | config read as admin | not required | not required | not required | `passed` | STT/TTS key names captured, values not printed | no UI screenshot/mobile microphone retest | Stage 2 media attachment sidecar remains current path |

## Capability Results

### Proven Native On This Runtime

- Admin API authentication with approved env credentials.
- User and group creation/deletion for synthetic proof actors.
- Group membership and Preview Access differentiation.
- Group-restricted Workspace Model visibility.
- Group-restricted shared prompt visibility and prompt history endpoint.
- Group-restricted Knowledge visibility and basic retrieval path.
- Synthetic TXT/PDF upload with processing.
- Synthetic DOCX/XLSX placeholder upload acceptance without valid OOXML or
  extraction-quality claims.
- Safe Web Search execution path for ordinary users under current global
  default.
- Native STT/TTS setting inventory through admin audio config.
- Non-admin chat delete behavior: deletion is allowed on this runtime.
- Manager negative controls: manager could not read inside personal chat, and
  outside user could not open the shared-link path tested.

### Requires Customer Decision

- Real department/group matrix.
- Manager/PO visibility policy and what counts as approved work visibility.
- Retention/no-delete/audit policy.
- Whether Web Search should remain globally enabled or be restricted by group.
- Whether native analytics is enough for first-stage reporting.
- Customer document/OCR/XLSX samples and data policy.

### Requires Custom Slice If Approved Requirement Exceeds Native Behavior

- Server-side delete guard if native `permissions.chat.delete` cannot enforce
  required no-delete behavior.
- Manager dashboard/export if explicit OpenWebUI sharing is not sufficient for
  supervisory visibility.
- Usage collector, billing gateway or provider gateway only if native analytics
  is insufficient.
- OCR/document extraction pipeline only after customer samples prove the native
  path is not enough.

## Evidence Handling

No screenshots were taken. No browser localStorage/sessionStorage dumps were
collected. No cookies, tokens, bearer headers, provider keys, `.env` contents,
private URLs, real emails or customer documents were saved.

The runtime proof summary recorded only synthetic actor names, non-secret API
setting paths, non-secret status codes, boolean visibility outcomes and counts.

## Gaps Remaining

- Screenshot-based Admin UI label proof was not collected.
- Analytics did not expose both synthetic users as rows during the run despite
  successful synthetic completions.
- Native no-delete is not currently enforced.
- Web Search group-only behavior cannot be claimed while global
  `permissions.features.web_search=true` remains unchanged.
- Manager positive visibility was not confirmed through the shared list path.
- Valid DOCX/XLSX parsing, OCR and complex spreadsheet behavior remain
  untested.
- Customer policy decisions are still required before any production rollout.

## Final Verdict

`admin_test_user_runtime_proof_partial_with_actor_matrix`

The credentials blocker is closed. The four-actor runtime matrix was executed
with synthetic actors and cleanup completed with no leftovers.

Native OpenWebUI capabilities are proven for RBAC/group membership, restricted
Workspace Model visibility, restricted prompt visibility, Knowledge
access/retrieval, TXT/PDF processing, DOCX/XLSX placeholder upload acceptance,
STT settings inventory and safe Web Search execution under the current global
default.

The proof remains partial because current runtime behavior does not satisfy
no-delete, does not prove group-scoped Web Search, does not show immediate
synthetic user analytics rows, and did not confirm positive manager shared-list
visibility without giving Manager/PO admin access.
