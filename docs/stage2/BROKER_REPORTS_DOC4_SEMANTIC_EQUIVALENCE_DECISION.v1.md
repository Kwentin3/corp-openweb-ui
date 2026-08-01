# Broker Reports DOC4 Semantic Equivalence Decision v1

Effective date: 2026-08-01

Status: `PROTOCOL_IMPLEMENTED; EXPERIMENT_BLOCKED_PROVIDER_FAILURE`

DOC4 uses four frozen real pairs (`real_pdf_1`, `real_pdf_2`, `real_pdf_4`, `real_pdf_5`) and one snapshot model. Each stateless PDF arm sees only the native PDF; each independent View arm sees only the complete LLM Document View. Prompts, schema, configuration, source identities and alternating run order are hash-bound before calls. RUN C is deterministic and source-blind. RUN D is independently source-grounded and prevents two matching wrong answers from proving parity.

All four gold checklists were independently sealed before provider calls and the
operator authorization was bound to the exact model, four source pairs, frozen
plan and allowed request bodies. Exact model-specific token counting then
stopped fail-closed: three separately frozen preflight attempts each received a
non-retryable HTTP 400 on the first `/responses/input_tokens` request. No token
count succeeded and no primary, stability, comparison or adjudication run
started. No truncation, chunking, model switch, RAG, retrieval, summarization,
repair, best-of selection, cross-arm session, tool, web, or product route was
used.

Terminal DOC4 experiment status:

```text
EXPERIMENT_PROTOCOL_FROZEN_BEFORE_RUNS = TRUE
PROVIDER_TRANSFER_AUTHORIZED = TRUE
EXACT_MODEL_CANDIDATE_FROZEN = TRUE
GOLD_CHECKLISTS_TOTAL = 4
GOLD_CHECKLIST_ITEMS_TOTAL = 461
GOLD_CRITICAL_FACTS_TOTAL = 321
GOLD_CHECKLISTS_CREATED_BEFORE_PROVIDER_CALLS = TRUE
ARM_ISOLATION = IMPLEMENTED; REAL_ARMS_NOT_RUN
CONTEXT_PREFLIGHT = BLOCKED_PROVIDER_HTTP_400
ELIGIBLE_DOCUMENTS_TOTAL = 0
COMPLETED_PAIRED_DOCUMENTS_TOTAL = 0
SOURCE_ADJUDICATION = NOT_EVALUATED
PROVIDER_CALLS_TOTAL = 3
PROVIDER_TOKENS = NOT_REPORTED
PROVIDER_COST = NOT_REPORTED
DOC4_EXPERIMENT_EXECUTION = BLOCKED
MODEL_TASK_ADEQUACY = NOT_EVALUATED
PDF_TO_LLM_VIEW_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_PROVIDER_FAILURE
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

The three failed calls are terminal preflight attempts, not model-task evidence.
The provider did not report token usage or cost for them. A future attempt needs
a new explicit model-or-policy decision and a newly frozen plan; these results
must not be rebadged as semantic evidence.
