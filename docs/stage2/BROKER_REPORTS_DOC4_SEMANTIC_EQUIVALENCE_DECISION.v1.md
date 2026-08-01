# Broker Reports DOC4 Semantic Equivalence Decision v1

Effective date: 2026-08-01

Status: `PROTOCOL_IMPLEMENTED; PREFLIGHT_PASSED; EXPERIMENT_BLOCKED_MODEL_OUTPUT_FAILURE`

DOC4 uses four frozen real pairs (`real_pdf_1`, `real_pdf_2`, `real_pdf_4`, `real_pdf_5`) and one snapshot model. Each PDF arm sees only the native PDF; each independent View arm sees only the complete LLM Document View. Prompts, schema, source identities, alternating order, gold and allowed request bodies are hash-bound before calls.

After explicit operator authorization, the minimal-request v5 preflight passed all eight exact token counts. All four documents fit the frozen 1,050,000-token window with the 65,536-token output reservation and 105,000-token margin.

The paired experiment then failed closed on the first arm. The `real_pdf_1` PDF request and its one exact replay both returned structured responses, but neither passed the deterministic semantic validator. Because no arm response was accepted, no PDF/View pair, deterministic comparison, stability replay, source adjudication, or terminal equivalence calculation completed. Matching or gap metrics therefore remain null, not zero.

```text
EXPERIMENT_PROTOCOL_FROZEN_BEFORE_RUNS = TRUE
PROVIDER_TRANSFER_AUTHORIZED = TRUE
STORE_PARAMETER = OMITTED
EXACT_MODEL_CANDIDATE_FROZEN = TRUE
GOLD_CHECKLISTS_TOTAL = 4
GOLD_CHECKLIST_ITEMS_TOTAL = 461
GOLD_CRITICAL_FACTS_TOTAL = 321
CONTEXT_PREFLIGHT = PASSED
SUCCESSFUL_TOKEN_COUNT_CALLS_TOTAL = 8
PREFLIGHT_INPUT_TOKENS_TOTAL = 152573
ELIGIBLE_DOCUMENTS_TOTAL = 4
FAILED_ARM = real_pdf_1/PDF
FAILED_ARM_RETURNED_RESPONSES_TOTAL = 2
COMPLETED_PRIMARY_ARMS_TOTAL = 0
COMPLETED_PAIRED_DOCUMENTS_TOTAL = 0
SOURCE_ADJUDICATION = NOT_EVALUATED
PRIMARY_PROVIDER_CALLS_TOTAL = NOT_RECONCILED_AFTER_FAILURE
DOC4_EXPERIMENT_EXECUTION = BLOCKED_TERMINAL_MODEL_OUTPUT_FAILURE
MODEL_TASK_ADEQUACY = FAILED_STRUCTURED_RESPONSE_CONTRACT
PDF_TO_LLM_VIEW_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_MODEL_OUTPUT_FAILURE
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

This is model-task evidence, but not semantic-equivalence evidence. The exact local validation reason and usage metadata from the failed historical arm were not persisted; the harness now preserves those private receipts prospectively. No further provider attempt is authorized by this result.
