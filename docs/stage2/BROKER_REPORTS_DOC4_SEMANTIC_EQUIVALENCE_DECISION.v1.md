# Broker Reports DOC4 Semantic Equivalence Decision v1

Effective date: 2026-08-01

Status: `PROTOCOL_IMPLEMENTED; EXPERIMENT_NOT_STARTED`

DOC4 uses four frozen real pairs (`real_pdf_1`, `real_pdf_2`, `real_pdf_4`, `real_pdf_5`) and one snapshot model. Each stateless PDF arm sees only the native PDF; each independent View arm sees only the complete LLM Document View. Prompts, schema, configuration, source identities and alternating run order are hash-bound before calls. RUN C is deterministic and source-blind. RUN D is independently source-grounded and prevents two matching wrong answers from proving parity.

The experiment cannot start until all four gold checklists are independently sealed before calls, exact model-specific token counts prove both full arms fit, and the private authorization file proves current organization/project policy plus explicit permission to send the client documents. No truncation, chunking, RAG, retrieval, summarization, repair, best-of selection, cross-arm session, tool, web, or product route exists.

Current implementation-stage status:

```text
EXPERIMENT_PROTOCOL_FROZEN_BEFORE_RUNS = FALSE
PROVIDER_TRANSFER_AUTHORIZED = FALSE
EXACT_MODEL_CANDIDATE_FROZEN = TRUE
GOLD_CHECKLISTS_CREATED_BEFORE_PROVIDER_CALLS = FALSE
ARM_ISOLATION = IMPLEMENTED_NOT_REAL_RUN_PROVEN
SOURCE_ADJUDICATION = NOT_STARTED
DOC4_EXPERIMENT_EXECUTION = BLOCKED
BLOCKER = PROVIDER_TRANSFER_NOT_AUTHORIZED
PDF_TO_LLM_VIEW_SEMANTIC_EQUIVALENCE = NOT_EVALUATED
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

These values are implementation-stage facts, not the terminal DOC4 receipt. A later proof branch may replace them only with hash-bound private evidence and safe aggregates.
