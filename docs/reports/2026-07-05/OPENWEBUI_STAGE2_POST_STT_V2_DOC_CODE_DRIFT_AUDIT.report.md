# OpenWebUI Stage 2 Post-STT-v2 Docs/Code Drift Audit Report

## 1. Summary

Date: 2026-07-05.

Verdict: `stage2_docs_code_drift_after_stt_v2_resolved`.

The audit found documentation drift after STT v2 closure. The code and recent
proof reports show that STT v2 current scope is closed: diarization/speaker
labels, structured transcript storage, `transcript_ref`, post-processing through
two native-prompt actions, same-chat quick actions and selected-message DOCX
export are implemented. Several living docs still described those items as
future work.

The fix is docs-only. No code, compose, env, contract document or historical
evidence report was changed.

## 2. Sources reviewed

Customer-facing and commercial docs:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`
- `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md`
- `docs/commercial/STAGE2_DOCS_REPRESENTATION_MODEL.md`
- `docs/commercial/STAGE2_SCOPE_RECONCILIATION_150K.md`
- `docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md`

Stage 2 living docs:

- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`

STT docs:

- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- `docs/stage2/context/STT_V2_TRANSCRIPT_POSTPROCESSING_CONTEXT_PACK.md`

Evidence reports used as history, not rewritten:

- `docs/reports/2026-07-02/STT_V2_GATE_1_2_IMPLEMENTATION_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATE_2_5_TARGET_RUNTIME_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATE_3_PROMPT_CATALOG_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATE_4_QUICK_ACTIONS_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_GATE_5_PROMPT_ACCESS_VERSION_PROOF.report.md`
- `docs/reports/2026-07-02/STT_V2_FINAL_CLOSEOUT_AND_PILOT_READINESS.report.md`
- `docs/reports/2026-07-03/STT_V2_NATIVE_PROMPT_QUICK_ACTION_IMPLEMENTATION.report.md`
- `docs/reports/2026-07-03/STT_V2_READABLE_RAW_TRANSCRIPT_PROJECTION.report.md`
- `docs/reports/2026-07-03/STT_V2_MESSAGE_DOCX_EXPORT_IMPLEMENTATION_PROOF.report.md`

## 3. Code/config audited

Read-only code/config areas:

- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/lemonfox.py`
- `services/stage2-stt/stage2_stt/provider.py`
- `services/stage2-stt/stage2_stt/jobs.py`
- `services/stage2-stt/stage2_stt/job_store.py`
- `services/stage2-stt/stage2_stt/storage.py`
- `services/stage2-stt/stage2_stt/validation.py`
- `services/stage2-stt/stage2_stt/artifact_store.py`
- `services/stage2-stt/stage2_stt/transcript_store.py`
- `services/stage2-stt/stage2_stt/post_processing.py`
- `services/stage2-stt/stage2_stt/message_docx.py`
- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`
- `deploy/openwebui-static/loader.js`
- `deploy/openwebui-static/stage2-stt-normalization.json`
- `services/stage2-stt/tests/`

Confirmed code/runtime surface:

- Action operations include `list_postprocessing_templates`,
  `execute_postprocessing`, `draft_postprocessing_prompt` and
  `export_message_docx`.
- Sidecar routes include post-processing template list, execute, prompt draft and
  `POST /stage2-api/message-docx/exports`.
- `TranscriptResultV1`, `PostProcessingResultV1` and
  `MessageDocxExportResultV1` are current contracts.
- `TranscriptStoreAdapter` creates opaque `art_...` refs and persists structured
  transcript results through ArtifactStore.
- `post_processing.py` builds speaker-aware transcript projections and refuses
  too-long single-pass transcript processing.
- `message_docx.py` uses `python-docx` through `DocxExportAdapterFactory` and
  supports `semantic_chat_v1`.
- Loader exposes post-processing actions and a DOCX button for completed
  assistant messages.

## 4. STT v2 closed evidence

Closed in current scope:

- Gate 1-2: diarization/speaker labels, `TranscriptResultV1`, ArtifactStore,
  opaque `transcript_ref`, fail-closed access and no unsafe provider output in
  user-facing paths.
- Gate 2.5: deployed sidecar/runtime proof with OpenWebUI healthy and
  `stage2-stt` up.
- Gate 3: OpenWebUI Prompt catalog with two STT templates.
- Gate 4: quick actions and same-chat post-processing bridge.
- Gate 5: prompt access, version/hash and changed/deleted prompt behavior.
- Gate 6: safe refusal for long transcript single-pass processing.
- Gate 8: selected completed assistant-message DOCX export with markdown-first
  `semantic_chat_v1`; operator save/open proof closed the browser gap.

## 5. Drift findings

| File | Section | Old/status found | Correct status | Action taken |
| --- | --- | --- | --- | --- |
| `STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` | F2 | `к реализации` | реализовано в пилотном объеме | updated |
| `STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` | F3 | `к реализации` | реализован стартовый набор: краткий пересказ и протокол встречи | updated |
| `STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` | F4 | `к реализации с проверкой` | реализовано через штатный раздел OpenWebUI Prompts | updated |
| `STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` | F5 | `к реализации` | реализовано в пилотном объеме при наличии говорящих от сервиса | updated |
| `STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` | F6 | `к реализации` | реализован экспорт отдельного ответа ассистента в DOCX | updated |
| `STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` | hour/status tables | STT v2 listed as future work | STT v2 current-scope work is done | updated |
| `STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md` | Documentation vs Code | no STT v2 route/action, no DOCX code | post-processing routes, Action operations, loader actions and DOCX endpoint exist | updated |
| `STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md` | Feature registry R2-R6 | `TO_IMPLEMENT_IN_CURRENT_SCOPE` | `DONE / CLOSED_IN_CURRENT_SCOPE` | updated |
| `STAGE2_DOCS_REPRESENTATION_MODEL.md` | Source-of-truth map | STT v2 described as current/to-implement | STT v2 described as closed with future extensions listed | updated |
| `ACCEPTANCE_MATRIX.md` | Audio/video transcription | base STT closure only | STT v2 post-processing, speaker-aware projection and DOCX export explicitly passed/closed | updated |
| `ENGINEERING_BACKLOG.md` | Current-stage closed | no explicit closed STT v2 section | closed STT v2 section added; future STT extensions separated | updated |
| `CONTEXT_INDEX.md` | STT route | STT MVP closed, but no full STT v2 closure routing | STT v2 closure and next broker epic routing added | updated |
| `README.md` | Next action | STT hardening only | next active functional epic is Broker reports / 3-НДФЛ pilot | updated |
| `IMPLEMENTATION_GATES.md` | STT gate notes | base MVP closure only | STT v2 current-scope closure added; future extensions require new gates | updated |
| `STT_V2_TRANSCRIPT_POSTPROCESSING_CONTEXT_PACK.md` | Executive summary/code map | pre-implementation status and outdated gaps | marked as pre-implementation context; current status and code map updated | updated |

No code/config drift requiring code changes was found. The drift was in living
docs lagging behind implemented/proven runtime state.

## 6. Documentation updates made

Updated files:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`
- `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md`
- `docs/commercial/STAGE2_DOCS_REPRESENTATION_MODEL.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/README.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/context/STT_V2_TRANSCRIPT_POSTPROCESSING_CONTEXT_PACK.md`
- this report

Historical commercial docs already carried historical notices and were not
rewritten.

## 7. Customer-facing wording updates

Customer-facing changes in `STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`:

- Replaced visible `Stage 2` wording with `Этап 2`.
- Replaced `Web Search` wording with `поиск в интернете` where customer wording
  did not need the English term.
- Replaced future STT v2 status with plain Russian closed-status wording.
- Avoided internal terms such as prompt hashes, ArtifactStore internals and
  Action implementation details.
- Kept Broker reports / XLS НДФЛ as `к реализации в ограниченном пилотном виде`.
- Kept F8-F11 as future packaging/readiness work.

## 8. Internal engineering updates

Internal docs now say:

- STT v2 post-processing is `DONE / CLOSED_IN_CURRENT_SCOPE`.
- Two starter templates are implemented: `Краткий пересказ` and
  `Протокол встречи`.
- Template management is closed for the MVP through native OpenWebUI Prompts.
- Speaker-aware output is closed when provider labels exist; exact real names are
  not guaranteed.
- DOCX export is a generic selected completed assistant-message feature, not
  STT-only.
- Broker reports / 3-НДФЛ is the recommended next active functional epic, still
  not implemented.

## 9. Remaining open / future STT items

Future STT work:

- chunking/map-reduce for long transcripts;
- OpenWebUI Prompt API Adapter;
- full additional transcript template set;
- specialized processed-result-only DOCX artifact path;
- separate Meetings app / transcript history UI;
- PDF export;
- branded Word templates;
- broader mobile/large-file/retention/permission hardening.

## 10. Next active Stage 2 epic recommendation

Recommended next active functional epic: Broker reports / XLS НДФЛ limited
pilot.

Reason: STT v2 current scope is closed, while Broker reports is already present
in customer-facing scope as a limited pilot and has fresh customer-question docs.
It must remain a pilot until customer methodology, examples and accepted input
formats are available.

## 11. Agent proposals

- Treat `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` as the main
  customer-facing source.
- Treat `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md` as the internal
  evidence bridge for commercial/status work.
- Treat STT v2 proof reports as historical evidence, not living status docs.
- Mark old context packs as historical/pre-implementation when they are useful
  but superseded.
- Before a customer demo, repeat: upload/transcribe media, confirm two transcript
  actions, confirm same-chat result, export one assistant message to DOCX and
  open it locally.

## 12. Financial/secret scan

Financial scan was run against `docs README.md` using the required
amount/financial-term pattern. The exact regex is not repeated here so the
report does not self-match the scan.

Final result: no matches.

Additional safety scan over updated docs found only guardrail wording and
document-type labels, not actual secrets, keys, private values or customer data.

## 13. Checks

Final checks:

- `git diff --name-only`: docs-only changes.
- `git diff --check`: exit code 0; Git printed LF-to-CRLF working-copy warnings
  only.
- Code/compose/env changes: none.

## 14. Final verdict

`stage2_docs_code_drift_after_stt_v2_resolved`
