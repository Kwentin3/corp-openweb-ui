# Broker Reports DOC4 PDF vs LLM Document View Closure Report

Status: `BLOCKED_PROVIDER_FAILURE`

Effective date: 2026-08-01

Implementation PR: `#253`

Implementation merge commit:
`3251769728df224f79d085f508c3a47d4e0b8d23`

Terminal harness commit:
`73a54d132648e62623a3c959aba54296390cb064`

## 1. Result

The inactive DOC4 harness implementation passed independent review, exact-head
CI and merged-main tests. The project operator authorized only the four frozen
DOC4 documents for the OpenAI API snapshot `gpt-5.4-2026-03-05` with
`store=false`.

The semantic experiment did not reach paired runs. Three separately frozen
context-preflight attempts each stopped on the first non-retryable HTTP 400
from `/responses/input_tokens`. No token count succeeded; no PDF arm, View arm,
stability replay, deterministic comparison or independent adjudication ran.

```text
DOC4_HARNESS_IMPLEMENTATION = PASSED
INDEPENDENT_REVIEW = PASSED
PROVIDER_TRANSFER_AUTHORIZED = TRUE
DOC4_EXPERIMENT_EXECUTION = BLOCKED
MODEL_TASK_ADEQUACY = NOT_EVALUATED
PDF_TO_LLM_VIEW_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_PROVIDER_FAILURE
```

## 2. Independent review and implementation merge

An isolated reviewer inspected commit
`093832ba56f65cc3566f7a4aeb67713ec072241f` without using author conclusions.
All 15 required boundaries passed: arm isolation, gold isolation, stateless
requests, deterministic non-LLM comparison, both-wrong handling, frozen
configuration, exact retry, native PDF, complete View, no truncation, validated
source pointers, private-output isolation and absent product route.

Actionable findings were zero. GitHub Actions run `30707928397` was green and
PR #253 merged as `3251769728df224f79d085f508c3a47d4e0b8d23`.

## 3. Gold checklists

Separate PDF-only agents visually inspected every page and received no LLM
View, Managed Document, arm response, comparison or desired conclusion. Every
checklist was source-grounded, schema-valid, SHA-256 sealed and immutable before
the first provider call.

| Safe ID | Gold items | Critical facts |
| --- | ---: | ---: |
| `real_pdf_1` | 42 | 27 |
| `real_pdf_2` | 50 | 18 |
| `real_pdf_4` | 295 | 229 |
| `real_pdf_5` | 74 | 47 |
| Total | 461 | 321 |

```text
GOLD_CHECKLISTS_TOTAL = 4
GOLD_CHECKLISTS_CREATED_BEFORE_PROVIDER_CALLS = TRUE
```

Private PDFs, Views, checklists, plans, authorizations and failure receipts
remain outside Git.

## 4. Context preflight and bounded fixes

Attempt 1 stopped on its first HTTP 400. The harness had included
response-generation-only fields in the token-count body. PR #254 bound the
allowlist to the exact filtered token-count bytes while leaving primary request
bytes unchanged. Its isolated review had zero findings, CI run `30710955283`
was green, and it merged as
`4f1bd35f1d9e355e8d4afd8714c931eb5e616f18`.

Attempt 2 also stopped on its first HTTP 400. The baseline stage sent empty
`input` and `instructions` placeholders. PR #255 omitted those absent fields
and kept the five cumulative stages and primary request unchanged. Its isolated
review had zero findings, CI run `30711467260` was green, and it merged as
`73a54d132648e62623a3c959aba54296390cb064`.

Attempt 3, frozen from that merged main, still received HTTP 400 on its first
token-count request. The no-endless-search boundary was then applied. Each 400
was non-retryable, so the reconciled count is three calls total and zero
transport retries. The original harness did not preserve the 400 response body;
the provider reported neither usage nor cost. The three attempts are
invalidated and are not semantic evidence.

```text
PREFLIGHT_ATTEMPTS_TOTAL = 3
SUCCESSFUL_TOKEN_COUNT_CALLS_TOTAL = 0
FAILED_TOKEN_COUNT_CALLS_TOTAL = 3
PROVIDER_CALLS_TOTAL = 3
PROVIDER_TOKENS = NOT_REPORTED
PROVIDER_COST = NOT_REPORTED
ELIGIBLE_DOCUMENTS_TOTAL = 0
ELIGIBILITY_STATUS = NOT_EVALUATED_PROVIDER_FAILURE
CONTEXT_LIMIT_INELIGIBLE_TOTAL = 0
```

`ELIGIBLE_DOCUMENTS_TOTAL=0` means no document reached an eligibility decision;
it does not mean that four documents exceeded the context window.

## 5. Arms, comparison and adjudication

Because exact context eligibility was not established, the primary run command
was not executed.

| Stage | Result |
| --- | --- |
| PDF arms | `NOT_EVALUATED` |
| View arms | `NOT_EVALUATED` |
| Completed paired documents | `0` |
| Cross-arm comparison | `NOT_EVALUATED` |
| Independent source adjudication | `NOT_EVALUATED` |
| Model stability | `NOT_RUN_PROVIDER_FAILURE` |

Precision, recall and cross-arm match rates are null, not zero. Artifact gaps,
both-wrong cases, unsupported critical facts and invalid model source pointers
are also not evaluated; reporting zero would falsely imply completed runs.

## 6. Validation and privacy

The original implementation and both bounded fixes passed isolated reviews
with zero actionable findings. The terminal merged main passed the full focused
Broker Reports suite:

```text
focused tests = 301 passed
test failures = 0
Ruff = PASSED
private artifacts in Git = 0
runtime product route changes = 0
live changes = 0
```

No model switch, fallback, document truncation, chunking, RAG, retrieval,
repair, best-of selection or product integration was introduced.

## 7. Terminal scope stop

DOC4 closes as an honest provider-preflight blocker. It does not prove model
adequacy and cannot answer PDF-to-View semantic equivalence. A future provider
attempt requires an explicit new model-or-policy decision and a newly frozen
plan; the three invalidated attempts must not be reused or rebadged.

```text
PDF_ARM_CRITICAL_PRECISION = NOT_EVALUATED
PDF_ARM_CRITICAL_RECALL = NOT_EVALUATED
VIEW_ARM_CRITICAL_PRECISION = NOT_EVALUATED
VIEW_ARM_CRITICAL_RECALL = NOT_EVALUATED
CRITICAL_CROSS_ARM_MATCH_RATE = NOT_EVALUATED
NONCRITICAL_CROSS_ARM_MATCH_RATE = NOT_EVALUATED
ARTIFACT_SEMANTIC_GAPS_TOTAL = NOT_EVALUATED
BOTH_ARMS_WRONG_TOTAL = NOT_EVALUATED
INVALID_SOURCE_POINTERS_TOTAL = NOT_EVALUATED
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
