# OfficeCLI: multiple XLSX product qualification, 2026-09-26

The ordinary chat workflow now works for `gpt-5.6-luna`, `gpt-5.4-mini` and
`claude-sonnet-4-6`: upload two XLSX files, ask for a derived workbook, receive
a native attachment, download it and check its contents. No file ID or tool
name was supplied by the user. Scope is deriving a new workbook from source
data; faithful cloning of complex workbooks with drawings is not qualified.

## Cause and owner

The original chat `878a0242-0944-44d5-b54b-ef9c34d87226` retained all uploaded
files. Re-uploading generated new IDs as expected. Four inspect calls omitted
`file_id`; the sidecar correctly rejected ambiguity with HTTP 422. In Default
function calling, the separate tool-selection request reads message text and
does not carry native file references. Tool selection also precedes RAG extraction.
This caused the model to miss IDs and suggest re-uploading instead of reading
the two existing sources. Historical prompts were not retained; source ordering
and stored calls establish the reconstruction, not a literal prompt capture.

| Meaning | Existing owner used |
| --- | --- |
| Upload, IDs, history, permissions | OpenWebUI Files and Chat services |
| IDs supplied to model | Native `add_file_context`, `<attached_files>` tags |
| Repeated inspect → create calls | OpenWebUI native tool loop |
| Eligible models and minimal instruction | Existing OfficeCLI Auto Attach Filter |
| Workbook commands and validation | OfficeCLI OpenAPI sidecar, CLI 1.0.148 |
| Output persistence and attachment | Native Files API and event channel |

The Filter selects native execution only for at least two distinct native XLSX
references and explicitly qualified models. It changes the shared metadata
params, because OpenWebUI 0.9.6 consumes ordinary params before Filter inlets.
It never fetches files or reconstructs a manifest. Tasks, explicit caller tools,
single files, duplicate references and unqualified models retain their route.
The instruction explains explicit IDs, source reads, creation versus editing,
valid sheet commands and the limits of annotated cell inspection.

## Product evidence

Synthetic sources are stored under `artifacts/officecli-multi-xlsx/`:
Jan rows A/2/100 and B/3/50; Feb rows A/4/120 and B/1/70.
User requested exactly two sheets, source columns, an Amount formula per row
and a SUM total, with no totals for Quantity or Price.

Every output below was downloaded through the native authenticated Files API.
`verify_workbook.py` checks exact sheet count/names, every source value, header,
row count, formulas, cached calculations and absence of Excel error cells.

| Model / scenario | Artifact | Result |
| --- | --- | --- |
| gpt-5.6-luna, fresh chat, admin | sales-mini.xlsx | PASS, two source inspect calls with explicit IDs, one create |
| gpt-5.4-mini, model switch | sales-gpt54.xlsx | PASS, two explicit source inspect calls, one create |
| Claude Sonnet 4.6, fresh chat, role user | sales-user-sonnet.xlsx | PASS, two explicit source inspect calls, one create |
| gpt-5.6-luna, fresh chat, role user | sales-user-luna.xlsx | PASS, two explicit source inspect calls, one create |
| gpt-5.6-luna, follow-up without re-upload, role user | sales-user-followup.xlsx | PASS, sources retained, two inspect calls, one create |

Each passing workbook has only `Янв26` and `Фев26`, formulas `=B2*C2`,
`=B3*C3`, `=SUM(D2:D3)` and cached totals 350/550. User-role downloads returned
200. The same user could not download an admin's private result (404).
The temporary role-user account, its ten synthetic files and three chats were
removed after retaining sanitized receipts and output bytes locally.

Reviewable retained chat: <https://gpt.alpha-soft.ru/c/09986988-0181-4e5e-aafc-916cc3152773>.
Its first two outputs prove explicit source reads and model switching. Later
Gemini attempts there are failed qualification, not passing evidence.
Initial candidates were rejected despite tool success: one omitted `parent`
and another retained an extra Sheet1. The final sheet instruction fixed both.

## Provider boundaries

Current gpt-5.6-luna Chat Completions rejected tools with default reasoning.
The qualified multi-XLSX route sets `reasoning_effort=none` only when no other
effort is explicitly requested; an explicit incompatible effort fails with a
clear message. No global provider transport/configuration was changed.
[OpenAI guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6)
describes Responses for reasoning with tools.

Gemini 3.5/3.6 Flash returned empty assistant output on the current native route.
A minimal call through the existing provider endpoint confirmed a streamed
tool call without `index`. Installed middleware only assembles calls having
that field. This matches [OpenWebUI issue 28492](https://github.com/open-webui/open-webui/issues/28492),
which also identifies the required Google thought-signature round trip.
No Gemini protocol monkeypatch, provider client or core overlay was added.
Gemini and untested Opus/Lite variants are excluded from the new qualification
valve. Their older OfficeCLI allowlist remains unchanged. Model-generated
attachment/sandbox links are not a separate download owner; use the native file
card. Final prose is not fully deterministic across models.

Official OfficeCLI [XLSX skill](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.148/skills/officecli-xlsx/SKILL.md)
supports `dump` → `batch`. An isolated synthetic experiment passed 7 commands
and validation with two sheets. This is a bounded capability experiment;
subtree dump does not qualify workbook drawings/resources or the original
business files. [CLI merge](https://github.com/iOfficeAI/OfficeCLI/wiki/command-merge)
fills template placeholders and is not a workbook-union operation.

## Release binding and rollback

- Filter version `0.9.0-multi-xlsx-native`, LF SHA-256
  `b4ea612001ffabd3c9a130816d671427c5df09974a37a3c0a015878525238d1d`.
- Production native Function readback: same SHA, Active/Global true.
- `multi_xlsx_native_model_ids=gpt-5.6-luna,gpt-5.4-mini,claude-sonnet-4-6`.
- `multi_xlsx_no_reasoning_model_ids=gpt-5.6-luna`.
- Existing eight-entry `target_model_ids` unchanged; new valves default empty.
- OpenWebUI 0.9.6 image ID
  `sha256:114f20df22d1e4f33e9381a5e75492db92310b98f61694e6f7e5f1c1c5336a6b`.
- Sidecar image ID
  `sha256:4a85142f866a43ba9a3678aff24816a5c97655827741c0e502a14ba2c751ac29`;
  CLI pinned 1.0.148. Neither container was rebuilt or restarted.

Focused Filter and sidecar regression suite: **60 passed**.
Run: `python -m pytest -q deploy/openwebui-functions/tests/test_officecli_auto_attach_filter.py services/officecli-openapi-proof/tests`.
Runbook updated with exact source hash, qualified valves and provider limitation.
To disable only automatic multi-XLSX routing, clear `multi_xlsx_native_model_ids`.
Pre-change Function/valves backup is retained locally outside the commit.
Repository work is isolated on `agent/officecli-multi-xlsx`, based on main
`bba9fa8c`; pre-existing dirty Broker work was preserved.
