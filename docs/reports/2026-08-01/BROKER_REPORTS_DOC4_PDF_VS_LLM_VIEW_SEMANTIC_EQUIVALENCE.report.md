# Broker Reports DOC4 PDF vs LLM Document View Closure Report

Status: `BLOCKED_TERMINAL_MODEL_OUTPUT_FAILURE`

Effective date: 2026-08-01

## 1. Result

The simplified request policy successfully reopened and passed context preflight. It did not complete the semantic experiment.

The operator authorized the same four frozen documents and OpenAI snapshot `gpt-5.4-2026-03-05`, with `store` omitted and provider-default retention acknowledged. The v5 preflight made one exact full-request token count for each PDF and View arm. All eight succeeded and all four documents were eligible.

The paired run stopped on its first arm, `real_pdf_1/PDF`. The original response and the one allowed exact replay both reached the local semantic validator and failed. No response was accepted, so the remaining seven primary arms and all four stability arms were not called.

```text
DOC4_HARNESS_IMPLEMENTATION = PASSED
PROVIDER_TRANSFER_AUTHORIZED = TRUE
CONTEXT_PREFLIGHT = PASSED
DOC4_EXPERIMENT_EXECUTION = BLOCKED_TERMINAL_MODEL_OUTPUT_FAILURE
MODEL_TASK_ADEQUACY = FAILED_STRUCTURED_RESPONSE_CONTRACT
PDF_TO_LLM_VIEW_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_MODEL_OUTPUT_FAILURE
```

## 2. Frozen gold and source scope

The same four PDF-only gold checklists remained sealed before provider calls.

| Safe ID | Gold items | Critical facts |
| --- | ---: | ---: |
| `real_pdf_1` | 42 | 27 |
| `real_pdf_2` | 50 | 18 |
| `real_pdf_4` | 295 | 229 |
| `real_pdf_5` | 74 | 47 |
| Total | 461 | 321 |

The v5 plan is bound by SHA-256 `9c5323cd766187593b5cf9d22e2f0bbd22e57d09293a8a402d71a05f8e2f3207`. PDFs, Views, gold, plans, authorizations, requests and responses remain outside Git.

## 3. Minimal request policy and strict schema repair

PR #257 removed `store`, explicit sampling, explicit reasoning and other unnecessary fields. Primary requests now contain only `model`, `instructions`, `input`, `max_output_tokens`, and `text`; token-count requests contain only `model`, `instructions`, `input`, and `text`. Exact-head CI run `30713899805` passed and the PR merged as `2cb2926e74d6e9ce8f925a60cdfe319038c8609d`.

The first simplified preflight call returned HTTP 400 because the strict response schema used `const` and `enum` nodes without explicit `type`. This proves `store` was not the blocker. PR #258 added every implicit type without changing the accepted value domain, added a recursive regression test, passed exact-head CI run `30714378698`, and merged as `d43149eb96b92fe1090d1af7139ec322ba050503`.

## 4. Successful context preflight

| Safe ID | PDF input tokens | View input tokens | Eligibility |
| --- | ---: | ---: | --- |
| `real_pdf_1` | 4,514 | 4,946 | `FIT` |
| `real_pdf_2` | 8,995 | 7,599 | `FIT` |
| `real_pdf_4` | 18,014 | 26,135 | `FIT` |
| `real_pdf_5` | 29,992 | 52,378 | `FIT` |
| Total | 61,515 | 91,058 | 4/4 eligible |

```text
SUCCESSFUL_TOKEN_COUNT_CALLS_TOTAL = 8
PREFLIGHT_INPUT_TOKENS_TOTAL = 152573
CONTEXT_LIMIT_INELIGIBLE_TOTAL = 0
CONTEXT_PREFLIGHT = PASSED
```

The provider did not report a cost for token counting.

## 5. Paired run blocker

The first PDF arm received two structured responses: the initial request and the contract-permitted exact replay. Both failed local semantic validation. Because the runner failed closed before writing an accepted arm, completed primary arms and paired documents remain zero.

The pre-closure runner preserved failed responses only after a successful arm return. Its exception therefore lost the two attempts' raw payload, exact validation reason, usage metadata and transport retry counts. We can prove that two responses reached validation, but cannot honestly reconstruct the exact HTTP-call or token totals. This closure adds a private terminal receipt carrying those fields for future runs; it does not retroactively invent the missing evidence and does not call the provider again.

| Stage | Result |
| --- | --- |
| Context preflight | `PASSED; 4/4 eligible` |
| `real_pdf_1` PDF arm | `FAILED_SEMANTIC_VALIDATION_AFTER_EXACT_RETRY` |
| Remaining primary arms | `NOT_RUN_FAIL_CLOSED` |
| Completed paired documents | `0` |
| Stability | `NOT_RUN_MODEL_OUTPUT_FAILURE` |
| Cross-arm comparison | `NOT_EVALUATED` |
| Source adjudication | `NOT_EVALUATED` |

Precision, recall, cross-arm match, artifact-gap, both-wrong and pointer metrics are null, not zero.

## 6. Validation and privacy

The request-policy and schema-type patches both passed exact-head GitHub CI before the next provider stage. The closure adds tests for immutable private preservation of every invalid structured-response attempt. No model switch, fallback, truncation, chunking, RAG, retrieval, best-of selection, product integration or live change was introduced.

## 7. Terminal scope stop

The candidate is inadequate for this frozen DOC4 output contract because it could not produce one accepted first-arm result across the exact permitted replay. That is enough to stop further attempts with the same candidate and policy, but not enough to compare PDF against View.

```text
PDF_ARM_CRITICAL_PRECISION = NOT_EVALUATED
VIEW_ARM_CRITICAL_PRECISION = NOT_EVALUATED
CRITICAL_CROSS_ARM_MATCH_RATE = NOT_EVALUATED
ARTIFACT_SEMANTIC_GAPS_TOTAL = NOT_EVALUATED
BOTH_ARMS_WRONG_TOTAL = NOT_EVALUATED
INVALID_SOURCE_POINTERS_TOTAL = NOT_EVALUATED
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

A future provider attempt requires an explicit new candidate or policy decision and a newly frozen plan. The failed arm cannot be rebadged as semantic-equivalence evidence.
