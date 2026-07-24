# Broker Reports — Gate 2 Goal 9: controlled production migration

Дата: 2026-07-24

Терминальный статус: `NOT_CLOSED`.

## Результат

Registry-driven production path реализован, смержен и атомарно выпущен на stage. Release, rollback/reapply proof и repository/live parity прошли. Однако обязательный bounded live proof не дошёл до `Gate2FinancialEvidenceProductionRuntime`: все доступные approved provider routes завершились fail-closed до записи новой schema. Поэтому production migration нельзя объявить завершённой.

## Что прошло

- shadow qualification Goal 7: `passed`;
- Gate 2-only checksum Goal 8: `3/3`;
- implementation PR: `#90`;
- verifier contract correction PR: `#91`;
- verifier route correction PR: `#92`;
- bounded target correction PR: `#93`;
- atomic release: `passed`;
- release ID: `broker-reports-efee1fede8d4`;
- source revision: `efee1fede8d4e1f70ff1c54ceb7ba6dfa11584f0`;
- manifest SHA-256: `09734d10f47760bf9f6519edbaaedc20e3ef0d29763dda71bfa6efade761d006`;
- rollback artifact: создан;
- rollback previous state restored: `true`;
- rollback candidate state restored: `true`;
- health checks: `3/3`;
- staging cleanup: `passed`;
- independent delivery verifier: `passed`;
- repository/live bundle parity: `exact`.

Release включил:

- `financial_evidence_enabled=true`;
- Registry version `broker_reports_gate2_financial_evidence_registry_v1`;
- schema `broker_reports_financial_evidence_inputs_v1`;
- context `broker_reports_gate2_financial_context_v1`;
- `legacy_read_policy=dual_read`;
- `write_policy=new_schema_only`;
- старый `semantic_selection_enabled=false`.

## Неизменённые поверхности

- Gate 1 Function: без изменения content identity;
- Gate 2 source Function: без изменения content identity;
- Action: без изменения;
- loader: без изменения;
- managed prompts: без изменения;
- image: без изменения.

Live hashes:

- Gate 1: `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519`;
- Gate 2 source: `d3ba38ed554d87e01a97d7dceaffee71eaa02c88375706477d819f4ccc83d503`;
- Gate 2 domain: `ea5d00a513542d82689c1434396e82ce4c21222fefd217292061fa78f46505e0`.

## Bounded production proof

Read-only live-profile preflight с production segmentation `table=8/text=12` прошёл все readiness и coverage guards. Для proof был выбран один source-local window: один selected ref, один domain package, один ожидаемый provider call.

Approved routes завершились до нового financial runtime:

- `openai_gpt`, `gpt-5.6-sol` и `gpt-5.6-luna`: `gate2_model_provider_quota_exceeded`;
- `google_gemini`, `models/gemini-3.5-flash` и `models/gemini-3.1-flash-lite`: `gate2_model_provider_error`;
- `anthropic_claude`, `claude-haiku-4-5-20251001`: `gate2_model_schema_response_format_rejected`.

Контракт не ослаблялся:

- free JSON не включался;
- fallback не включался;
- schema repair не скрывался;
- Gate 3 оставался выключен;
- answer-context handoff был выключен как out-of-scope;
- persisted legacy artifacts не переписывались.

После каждой попытки:

- preexisting artifacts unchanged: `true`;
- new financial inputs/context/receipt/run: `0/0/0/0`;
- Gate 1/source Function identity unchanged: `true`;
- Knowledge/RAG/vector delta: `0`.

## Незакрытый инвариант

`A bounded live scope did not persist the new financial run, receipt, context and input artifacts.`

Primary evidence: safe provider terminal codes и нулевые new-schema artifact counts.

Owning component: stage provider availability и strict response-format capability до входа в `Gate2FinancialEvidenceProductionRuntime`.

Blocker type: `external_provider_state`.

Narrowest corrective slice: восстановить funded OpenAI Gate 2 capacity и повторить тот же bounded migration verifier без изменения runtime contracts.

## Privacy

Customer labels, values, filenames, private refs и provider raw output в Git не добавлены. Private diagnostic scripts и live payloads остаются только в ignored `local/` и private ArtifactStore.
