# OpenWebUI Broker Reports Gate 2: рефакторинг LLM-контекста и повтор одного PDF

Дата: 2026-07-12

Case: `customer_case_group_002_process_false_gate1_20260712145140`

Финальный private document packet: `art_sCKVXr4llYOiuTda1OidYnfhkUBYFF_7`

## Вердикт

`GATE2_LLM_CONTEXT_REFACTOR_PARTIAL`

Контекст и provider path существенно улучшены. Полное покрытие пока не доказано, поэтому `BROKER_REPORTS_SINGLE_PDF_E2E_PASSED` и `READY_FOR_LIMITED_MULTI_DOCUMENT_CASE_PROOF` не заявляются.

Подтверждены:

- `GATE2_LLM_FRIENDLY_PACKAGE_CONTRACT_READY`
- `GATE2_DOMAIN_APPLICABILITY_FILTER_READY`
- `GATE2_PACKAGE_FEASIBILITY_GUARD_READY`
- `GATE2_DOCUMENT_SUMMARY_EVIDENCE_BOUNDARY_READY`
- `GATE2_PROVIDER_SCHEMA_COMPATIBILITY_READY`
- `GATE2_LLM_CONTEXT_BOUNDED_CORPUS_PASSED`
- `GATE2_LLM_CONTEXT_REFACTOR_DEPLOYED`
- `GATE2_SINGLE_PDF_CONTEXT_RECOVERY_RERUN_COMPLETED`

## Реализация

- `broker_reports_gate2_llm_context_package_v2` с compact identity, target refs, local structure, headers, candidates, relations, domain task, issues и response contract;
- безопасный profiler, component accounting, duplicate detection и inspection view;
- auditable domain applicability;
- text без механически видимого business signal закрывается deterministic no-fact;
- `document_summary_evidence` не вызывается без summary candidate;
- feasibility guard для roles, role groups, relations и provenance;
- hard budgets без silent truncation;
- compact flat strict schema с bounded candidate/role/path enums;
- Gemini adapter сохраняет candidate-binding enums;
- managed Prompt понимает v2 package;
- соседние segments исполняются одним production run без объединения LLM packages.

## Bounded corpus

- 9 окон и 11 domain packages;
- 5 невозможных packages заблокированы до LLM;
- 6/6 provider calls прошли;
- 44 207 input tokens;
- 0 Gemini HTTP 400 и 0 validation errors на допустимых packages;
- 6 accepted packages;
- typed domains: `cash_movement`, `fee_commission`, `withholding_tax`;
- unknown/no-fact paths подтверждены;
- repair, fallback и hidden failover не использовались.

## Baseline против результата

| Метрика | Baseline | После рефакторинга |
|---|---:|---:|
| Orchestration windows | 116 | 51 batched / 335 derived segments |
| Domain packages | 175 | 192 |
| Mechanically impossible до LLM | 0 | 146 |
| Provider calls | 175 | 46 |
| Input tokens | 4 584 773 | 237 725 |
| Output tokens | 79 902 | 29 589 |
| Wall time, s | 4 209,349 | 2 247,726 |
| Provider/schema errors | 51 | 0 |
| Accepted packages | 55 | 43 |
| Rejected packages | 120 | 149, из них 146 pre-provider blockers |
| Provenance errors | 113 | 11 |
| Required-role/group validation errors | 70 | 0; невозможные блокируются до LLM |
| Typed owned refs | 1 | 40 |
| Unknown refs | 16 | 13 |
| No-fact refs | 297 | 2 205 |
| Uncovered refs | 2 175 | 231 |
| Conflict refs | 0 | 0 |

Input tokens снижены на 94,8%, calls — на 73,7%, uncovered refs — на 89,4%.

## Факты и provider

- `cash_movement`: 22;
- `fee_commission`: 15;
- `withholding_tax`: 3;
- `unknown_source_row`: 13.

Все 46 calls прошли через `google_gemini` / `models/gemini-3.1-flash-lite` с strict `json_schema`: HTTP 400 — 0, repair/fallback/failover — 0, total tokens — 267 314, provider duration — 139 371 ms.

## Coverage и ограничения

Parent accounting: 2489/2489 refs, без duplicate/unaccounted parent refs и silent truncation.

- typed-owned: 40;
- unknown: 13;
- no-fact: 2205;
- uncovered: 231;
- conflict: 0.

Основной uncovered связан с typed feasibility blockers: unavailable roles, role groups, relations и один context budget blocker.

Остались две узкие ошибки допустимых packages:

1. Два `unknown_source_row` packages на 1 и 10 refs дали 11 `source_fact_provenance_missing`: unknown выбран без bindings, а неизменённый validator требует original value provenance.
2. Один `fee_commission` package дал `candidate_binding_contract_mismatch` при одном result с тремя selections.

Validator, provenance и ownership требования не ослаблялись.

## Guards и readiness

Document/file/Knowledge/vector delta — 0. OCR/VLM и Gate 3/tax/declaration/XLS/XLSX не запускались. OpenWebUI core не менялся.

Следующий bounded slice: deterministic unknown terminal ownership с source-value provenance и устранение единичного fee package identity mismatch. До этого multi-document proof преждевременен.
