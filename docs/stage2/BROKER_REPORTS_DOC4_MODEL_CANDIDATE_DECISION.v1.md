# Broker Reports DOC4 Model Candidate Decision v1

Effective date: 2026-08-01

Status: `CANDIDATE_FROZEN; PREFLIGHT_PASSED; MODEL_OUTPUT_CONTRACT_FAILED`

## Decision

The DOC4 measurement candidate remains OpenAI `gpt-5.4-2026-03-05` through the Responses API. The dated snapshot is an experiment instrument only; it is not production qualification, admission, fallback, valve, or activation.

## Official-source findings

| Property | Checked 2026-08-01 conclusion | Authority |
| --- | --- | --- |
| Exact identity | `gpt-5.4-2026-03-05` is an official snapshot intended to lock behavior. | [GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4) |
| Context/output | Context window is 1,050,000 tokens; maximum output is 128,000 tokens. | [GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4) |
| PDF | Responses `input_file` sends PDF text and page images to vision-capable models; inline Base64 PDF is supported. | [File inputs](https://developers.openai.com/api/docs/guides/file-inputs) |
| Structured output | GPT-5.4 supports Structured Outputs. DOC4 uses `text.format` with `json_schema` and `strict=true`, without tools. | [GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) |
| Exact counting | `/v1/responses/input_tokens` accepts the Responses request shape and returns the model-received input count. | [Counting tokens](https://developers.openai.com/api/docs/guides/token-counting) |
| Training | API data is not used for training unless the organization explicitly opts in. | [Data controls](https://developers.openai.com/api/docs/guides/your-data) |
| Retention | With `store` omitted, provider-default Responses application-state retention applies. The operator explicitly acknowledged that boundary; it is not a ZDR claim. | [Data controls](https://developers.openai.com/api/docs/guides/your-data) |

## Frozen minimal configuration

```text
provider = openai
request_model_id = gpt-5.4-2026-03-05
resolved_model_version_or_fingerprint = gpt-5.4-2026-03-05
context_window = 1050000
maximum_output_tokens = 128000
reserved_max_output_tokens = 65536
safety_margin_tokens = 105000
sampling parameters = omitted provider defaults
reasoning = omitted provider default
structured output = responses.text.format.json_schema.strict
PDF input = inline Base64 application/pdf, detail=high
token counting = one exact full-request count per arm
tools/web/retrieval/grounding = disabled
store parameter = omitted
```

The primary request contains only `model`, `instructions`, `input`, `max_output_tokens`, and `text`. The token-count request contains only `model`, `instructions`, `input`, and `text`.

## Authorized rerun and terminal result

The project operator explicitly authorized the same four frozen pairs and model with `store` omitted and provider-default retention acknowledged. PR #257 implemented that policy and merged as `2cb2926e74d6e9ce8f925a60cdfe319038c8609d` after exact-head CI run `30713899805` passed.

The first simplified preflight request reached OpenAI but exposed an explicit-type defect in the strict response schema. PR #258 declared types for all `enum` and `const` nodes, passed exact-head CI run `30714378698`, and merged as `d43149eb96b92fe1090d1af7139ec322ba050503`.

The newly frozen v5 preflight then passed all eight exact counts. All four PDF/View pairs fit the context window. The paired run stopped on the first `real_pdf_1` PDF arm: two returned structured responses, including the one permitted exact replay, both failed the local semantic validator. No View arm, completed pair, stability replay, comparison, or adjudication followed.

The historical runner discarded the failed arm metadata while unwinding, so its exact HTTP-attempt and usage totals cannot be reconstructed. This closure fixes that receipt gap prospectively without making another provider call. The same candidate/request may not be retried again without a new explicit model-or-policy decision.

```text
PROVIDER_TRANSFER_AUTHORIZED = TRUE
STORE_PARAMETER = OMITTED
CONTEXT_PREFLIGHT = PASSED
SUCCESSFUL_TOKEN_COUNT_CALLS = 8
ELIGIBLE_DOCUMENTS_TOTAL = 4
FAILED_ARM_RETURNED_RESPONSES_TOTAL = 2
PRIMARY_MODEL_CALLS_TOTAL = NOT_RECONCILED_AFTER_FAILURE
MODEL_TASK_ADEQUACY = FAILED_STRUCTURED_RESPONSE_CONTRACT
PDF_TO_LLM_VIEW_SEMANTIC_EQUIVALENCE = INCONCLUSIVE_MODEL_OUTPUT_FAILURE
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
