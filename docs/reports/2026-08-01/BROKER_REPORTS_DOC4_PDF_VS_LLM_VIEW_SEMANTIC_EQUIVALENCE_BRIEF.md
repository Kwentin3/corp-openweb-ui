# Broker Reports DOC4 PDF vs LLM View Brief

Status: `BLOCKED_TERMINAL_MODEL_OUTPUT_FAILURE`

Effective date: 2026-08-01

## Decision

The operator-authorized simplified OpenAI request omitted `store`, sampling and reasoning fields. This disproved the hypothesis that `store=false` caused the earlier blocker: the minimal v5 preflight passed all eight token counts, and all four PDF/View pairs fit the model context.

The paired run then stopped on the first `real_pdf_1` PDF arm. The original request and one exact replay both returned structured responses, but both failed the deterministic semantic validator. Fail-closed execution prevented every later arm, comparison, stability replay and adjudication.

## Measured outcome

```text
successful preflight calls = 8
preflight input tokens = 152573
eligible documents = 4
failed arm returned responses = 2
completed primary arms = 0
completed paired documents = 0
stability calls = 0
PDF/View metrics = NOT_EVALUATED
primary HTTP calls and usage = NOT_RECONCILED_AFTER_FAILURE
provider cost = NOT_REPORTED
```

## Terminal status

```text
DOC4_HARNESS_IMPLEMENTATION = PASSED
PROVIDER_TRANSFER_AUTHORIZED = TRUE
STORE_PARAMETER = OMITTED
CONTEXT_PREFLIGHT = PASSED
DOC4_EXPERIMENT_EXECUTION = BLOCKED_TERMINAL_MODEL_OUTPUT_FAILURE
MODEL_TASK_ADEQUACY = FAILED_STRUCTURED_RESPONSE_CONTRACT
PDF_TO_LLM_VIEW_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_MODEL_OUTPUT_FAILURE
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

Private source and provider evidence remains outside Git. No product route, fallback, truncation, chunking, RAG, retrieval, repair or live state was added. The runner now preserves future invalid-response receipts, but this historical arm is not retried; a new candidate or policy requires explicit operator authorization.
