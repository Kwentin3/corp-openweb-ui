# Broker Reports DOC4 PDF vs LLM View Brief

Status: `BLOCKED_PROVIDER_FAILURE`

Effective date: 2026-08-01

## Decision

The inactive DOC4 harness is implemented, independently reviewed and merged.
The operator authorized the four frozen PDF/View pairs for OpenAI
`gpt-5.4-2026-03-05` with `store=false`. Four PDF-only gold checklists were
sealed before provider calls: 461 items, including 321 critical facts.

Exact context preflight did not complete. Three separately frozen attempts each
received a non-retryable HTTP 400 on the first `/responses/input_tokens` call.
Two bounded request-shape defects were fixed through reviewed, CI-green PRs
#254 and #255; the third merged-main attempt still returned HTTP 400. The
no-endless-search stop was applied.

## Measured outcome

```text
provider calls = 3
successful token-count calls = 0
primary/stability calls = 0
provider tokens = NOT_REPORTED
provider cost = NOT_REPORTED
eligible documents = 0 (not evaluated)
completed paired documents = 0
PDF/View metrics = NOT_EVALUATED
adjudication = NOT_EVALUATED
```

## Terminal status

```text
DOC4_HARNESS_IMPLEMENTATION = PASSED
INDEPENDENT_REVIEW = PASSED
PROVIDER_TRANSFER_AUTHORIZED = TRUE
GOLD_CHECKLISTS_TOTAL = 4
DOC4_EXPERIMENT_EXECUTION = BLOCKED
MODEL_TASK_ADEQUACY = NOT_EVALUATED
PDF_TO_LLM_VIEW_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_PROVIDER_FAILURE
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

Private source and experiment artifacts remain outside Git. No product route,
live state, model fallback, truncation, chunking, RAG, retrieval or repair was
added. Any future provider attempt requires an explicit new model-or-policy
decision and a newly frozen plan.
