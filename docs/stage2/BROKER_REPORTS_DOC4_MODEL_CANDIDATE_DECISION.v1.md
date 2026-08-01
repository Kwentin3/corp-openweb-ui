# Broker Reports DOC4 Model Candidate Decision v1

Effective date: 2026-08-01

Status: `CANDIDATE_FROZEN_IMPLEMENTATION; OPERATOR_TRANSFER_AUTHORIZED`

## Decision

The one DOC4 measurement candidate is OpenAI `gpt-5.4-2026-03-05` through the Responses API. The dated snapshot is chosen over a floating current alias because a positive strict result requires reproducible model identity. This is an experiment instrument only; it is not production qualification, admission, fallback, valve, or activation.

## Official-source findings

| Property | Checked 2026-08-01 conclusion | Authority |
| --- | --- | --- |
| Exact identity | `gpt-5.4-2026-03-05` is an official snapshot intended to lock behavior. | [GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4) |
| Context/output | Context window is 1,050,000 tokens; maximum output is 128,000 tokens. | [GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4) |
| PDF | Responses `input_file` sends both extracted PDF text and page images to vision-capable models; inline Base64 PDF is supported. Detail is frozen to `high`. | [File inputs](https://developers.openai.com/api/docs/guides/file-inputs) |
| PDF limits | Each file and all files combined in one request must be under 50 MB. The official file-input guide publishes no separate page-count ceiling; exact model token eligibility remains mandatory. | [File-input usage considerations](https://developers.openai.com/api/docs/guides/file-inputs#usage-considerations) |
| Structured output | GPT-5.4 supports Structured Outputs. DOC4 uses `text.format` with `json_schema` and `strict=true`, without function/tool calling. | [GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) |
| Exact counting | `/v1/responses/input_tokens` accepts the Responses input shape, including files and schemas, and returns the exact model-received count. | [Counting tokens](https://developers.openai.com/api/docs/guides/token-counting) |
| Training | API data is not used for training unless the organization explicitly opts in. This general policy does not establish this organization's setting. | [Data controls](https://developers.openai.com/api/docs/guides/your-data) |
| Retention | Responses are eligible for ZDR, but default abuse-monitoring logs may retain customer content up to 30 days. Organization/project ZDR, processing region, logging and operator-access terms must be verified before private transfer. | [Data controls and retention table](https://developers.openai.com/api/docs/guides/your-data#storage-requirements-and-retention-controls-per-endpoint) |

## Frozen configuration

```text
provider = openai
request_model_id = gpt-5.4-2026-03-05
resolved_model_version_or_fingerprint = gpt-5.4-2026-03-05
MODEL_IDENTITY_IMMUTABLE = TRUE
API version = OpenAI Responses API v1
SDK = none; requests==2.32.5 direct HTTPS
context_window = 1050000
maximum_output_tokens = 128000
reserved_max_output_tokens = 65536
safety_margin_tokens = 105000
reasoning.effort = none
temperature = 0
top_p = 1
seed = unsupported/null
structured output = responses.text.format.json_schema.strict
PDF input = inline Base64 application/pdf, detail=high
token counting = responses.input_tokens exact endpoint
tools/web/retrieval/grounding = disabled
store = false
```

## Operator authorization and API preflight

No provider request was made during candidate selection or implementation. The project operator explicitly authorized the bounded DOC4 transfer of `real_pdf_1`, `real_pdf_2`, `real_pdf_4`, and `real_pdf_5` to the OpenAI API using `gpt-5.4-2026-03-05` with `store=false`. Exact model access, snapshot echo, schema acceptance, token-count acceptance for PDF, and response-size sufficiency remain to be measured by the frozen experiment.

The configured local key and canonical base URL remain credentials only; the separate operator receipt is the transfer authority.

```text
PROVIDER_TRANSFER_AUTHORIZED = TRUE
AUTHORIZATION_BASIS_STATUS = PROJECT_OPERATOR_APPROVED
PRIVATE_PROVIDER_CALLS = 0
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
