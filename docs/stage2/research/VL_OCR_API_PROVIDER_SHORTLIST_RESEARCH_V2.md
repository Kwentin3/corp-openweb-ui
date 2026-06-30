# VL OCR API Provider Shortlist Research V2

Date: 2026-06-25

Status: research only. No runtime proof, no provider accounts, no OpenWebUI
configuration changes, no customer documents and no production provider choice.

## 1. Corrected Scope

This research corrects the previous provider shortlist scope. The target is not
generic OCR and not a classic Document AI baseline.

The target is an API-accessible OCR-VL / vision-language document parsing path:

```text
raster image upload -> hosted OCR-VL/VLM document API -> structured JSON/text/tables -> LLM context
```

In scope:

- dedicated OCR-VL / vision-language OCR APIs;
- hosted Qwen-OCR / Qwen-VL / Qwen3-VL APIs;
- hosted PaddleOCR-VL APIs or very simple managed/serverless paths;
- hosted VLM document parsing services that accept images/PDFs and return
  structured output;
- generic VLM APIs only as backup.

Out of main scope:

- plain OCR without document-understanding/VLM layer;
- self-hosted/local GPU inference for the MVP;
- Azure Document Intelligence, Google Document AI, AWS Textract, OCR.space and
  Mistral OCR as primary shortlist candidates.

Those baseline services can still be useful as control systems, but they should
not define the main OCR-VL shortlist.

## 2. Difference From Previous Research

The previous research remains useful as a broad baseline, but it mixed three
different categories:

1. classic OCR / Document AI;
2. hosted OCR-VL / VLM document parsing;
3. generic vision LLM APIs.

V2 treats them separately:

- **main shortlist**: Alibaba Qwen-OCR/Qwen-VL, Datalab Chandra, and a hosted
  PaddleOCR-VL path;
- **benchmark backup**: Together/Gemini/Claude/OpenAI generic VLM APIs;
- **baseline only**: Mistral OCR, Azure Document Intelligence, Google Document
  AI, AWS Textract, OCR.space.

## 3. MVP Target Flow

The first implementation-facing flow should stay narrow:

1. OpenWebUI accepts a raster image from the user.
2. Backend classifies the file as an image document input.
3. Backend sends the image to one selected external OCR-VL/VLM document API
   through a server-side adapter.
4. The provider returns text, Markdown, JSON, tables, fields, bounding boxes or
   confidence when available.
5. Backend normalizes provider output into `DocumentExtractionResultV1`.
6. LLM receives the normalized extraction as context.
7. User sees the answer with a clear "recognized content" boundary.

Do not let the LLM directly treat the image as the final source of truth for the
Stage 2 MVP. The OCR/VL extraction result should be an explicit intermediate
artifact.

## 4. OCR-VL / VLM API Provider Matrix

| Provider / service | Hosted model / engine | Class | API available | Input / output | JSON/schema | Commercial verification | MVP suitability | Create account now |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Alibaba Cloud Model Studio / DashScope | Qwen3.5-OCR, Qwen-VL-OCR, Qwen3-VL Flash/Plus | Dedicated OCR-VL plus VLM | Yes: DashScope SDK and OpenAI-compatible endpoint | Images; Qwen OCR Response API supports images and PDFs; output text/JSON by prompt | JSON mode exists for supported Qwen models; OCR examples return JSON by instruction | Account terms and usage units must be verified outside GitHub. | Strong first candidate: dedicated Qwen-OCR, low adapter friction, JSON path | Yes |
| Datalab | Chandra OCR 2 / hosted conversion and extraction APIs | Hosted OCR-VL/document parsing service | Yes: REST API with `X-API-Key` | PDF, images and office docs; Markdown/HTML/JSON/chunks; structured extraction | JSON schema extraction API; citations/bboxes for auditability | Account terms and usage metadata must be verified outside GitHub. | Strong first candidate for document parsing, tables, forms and audit metadata | Yes |
| PaddleOCR official website / Baidu AI Studio | PaddleOCR-VL official API / MCP | Dedicated PaddleOCR-VL API path | Yes, but account/API URL/token must be verified manually | Images/PDFs; Markdown-oriented document parsing | Native output is parsing/Markdown; JSON may need adapter post-processing | Account terms need verification. | Best official Paddle path, but account/region friction is the risk | Yes, as Paddle track |
| WaveSpeedAI | Paddle OCR / PaddleOCR-VL REST API | Hosted PaddleOCR-VL-like REST API | Public model page advertises REST API | Images/doc parsing; JSON/Markdown claims need account proof | Likely JSON/Markdown, needs live account check | Account terms need verification. | Good replacement if official Paddle account is slow | Conditional |
| Novita AI | `paddlepaddle/paddleocr-vl` | Hosted model catalog / on-demand deployment | Model page exists; on-demand deployment, serverless not supported | Text+image input; text output | No clear schema support in public page | Third-party commercial signals conflict with the official deployment page; verify in account. | Useful experimental Paddle path, but not first if it requires GPU deployment | Conditional |
| Fireworks AI | `accounts/fireworks/models/paddleocr-vl-1-6` | Managed on-demand deployment | Yes after deploy-on-demand | Image input; 131k context | No function calling; schema support not shown for this model | On-demand GPU deployment terms; not a simple per-call account until proven. | Good managed benchmark if Fireworks is already acceptable; not first simple MVP account | No for first wave |
| Together AI | Qwen2.5-VL / Gemma vision examples | Generic VLM API with OCR examples | Yes; OpenAI-like API | Images; structured JSON examples | Supports structured output in docs | Serverless usage terms need account verification. | Good backup if dedicated OCR-VL services fail | Optional |
| Google Gemini API | Gemini Flash/Lite/Pro vision | Generic VLM backup | Yes | Images/PDF/document prompts | Structured output docs exist | Image/document usage terms need account verification. | Backup for image-to-JSON tests, not dedicated OCR-VL | Optional |
| Anthropic Claude API | Claude vision / PDF support | Generic VLM backup | Yes | Images and PDFs; PDF pages cost tokens | Structured output via tool/schema patterns | Token/image usage accounting needs account verification. | Strong general document reasoning backup, not dedicated OCR-VL | Optional |
| OpenAI API | Vision-capable models | Generic VLM backup | Yes | Images; structured outputs | Strong JSON schema support | Token/image usage terms need account verification. | Useful if an OpenAI account already exists; not dedicated OCR-VL | Optional |
| Mistral OCR / Azure DI / Google Document AI / AWS Textract / OCR.space | OCR/Document AI | Baseline only | Yes | OCR/document extraction | Varies | Usually page-based | Control baseline only; not the main OCR-VL path | No for V2 main shortlist |

## 5. Hosted PaddleOCR-VL Findings

The PaddleOCR-VL market is the easiest place to make a false assumption. A model
card is not the same as a usable API.

### PaddleOCR-VL Path Classification

| Path | Type | Real hosted API? | Needs GPU deployment? | Notes | Current MVP verdict |
| --- | --- | --- | --- | --- | --- |
| PaddleOCR official website / AI Studio | Official API / MCP path | Appears yes | No for website API path | LangChain and Haystack integrations say API URL and token come from the PaddleOCR official website / AI Studio. Official Baidu docs describe PaddleOCR-VL API usage and MCP services. | Best Paddle-first account to try, with manual account proof required. |
| WaveSpeedAI Paddle OCR | Hosted REST API | Appears yes | No, according to public page/blog claims | Public material positions it as ready REST API with no cold starts. Need account proof for output schema, commercial terms and retention. | Good fallback if official Paddle path has region/account friction. |
| Novita AI PaddleOCR-VL | Model catalog / on-demand deployment | Partly | Public page says on-demand deployment; serverless not supported | Supports image input and 16k context/output. Public page lists output as text. Third-party commercial calculators exist, but official terms should be verified. | Good experimental path, not a clean first-account choice until deployment/API details are proven. |
| Fireworks PaddleOCR-VL 1.6 | Managed on-demand deployment | Yes after deployment | Yes, dedicated deployment | Public model page says deploy-on-demand, serverless not supported, image input supported, 131k context. | Useful if managed GPU deployment is acceptable; not the simplest immediate API path. |
| Hugging Face Inference Providers | Model card/provider catalog | No direct deployed provider found | N/A | PaddleOCR-VL model cards exist, but no reliable hosted Inference Provider path was found. | Not now. |
| RunPod serverless | Custom serverless GPU endpoint | Not as ready model API | Yes, requires packaging/deployment | Valid future infra option, but it is deployment work rather than a provider account. | Out of MVP shortlist. |
| Replicate / fal.ai / Baseten / Together for PaddleOCR-VL | Provider search | No clear current direct hosted PaddleOCR-VL model found | Varies | Treat as "not found" until a model/API page is proven. | Not now. |

Practical conclusion: use one Paddle track in the first benchmark, but do not
assume every PaddleOCR-VL page is a ready API. Start with the official
PaddleOCR/AI Studio path; if account friction blocks it, try WaveSpeedAI, then
Novita.

## 6. Alibaba / Qwen Findings

Alibaba Model Studio is the strongest corrected-scope first candidate.

Relevant facts:

- Qwen-OCR is documented as a visual understanding OCR model for scanned
  documents, tables, receipts, information extraction, table parsing, formula
  recognition and document parsing.
- The current Qwen-OCR family includes `qwen3.5-ocr` and `qwen-vl-ocr`
  variants. Older versions are explicitly not recommended in the docs.
- Qwen-OCR can be called through DashScope SDK and through an
  OpenAI-compatible endpoint.
- DashScope exposes advanced OCR options more directly. OpenAI-compatible mode
  is easier for adapter reuse, but some OCR-specific knobs must be simulated by
  prompt.
- Qwen OCR Response API support is documented for images and PDFs for
  `qwen3.5-ocr` and later models.
- Qwen structured output / JSON mode is documented for supported Qwen models,
  including Qwen-VL non-thinking model families. Thinking mode has structured
  output limitations.
- Image billing is token-based. Alibaba docs describe visual token formulas:
  Qwen3-VL/Qwen-VL models use 32x32 pixel visual tokens; Qwen2.5-VL uses 28x28
  pixel visual tokens. The actual billable token count must be taken from API
  response usage.
- API keys and base URLs are region-specific. The docs show Singapore and China
  examples; account setup must confirm available region and data policy.
- Russian appears in official OCR examples and PaddleOCR-VL explicitly lists
  Cyrillic/Russian support. This is a capability signal, not production quality
  proof.

Recommended Qwen order for benchmark:

1. `qwen3.5-ocr` or current stable Qwen-OCR model for OCR/document parsing.
2. `qwen-vl-ocr` stable/latest if the account exposes it more directly.
3. `qwen3-vl-flash` or `qwen3-vl-plus` only as generic VLM fallback or for
   structured JSON comparison.

Adapter implication: build a native `QwenOcrAdapter` shape, not only a generic
OpenAI-compatible adapter. The OpenAI-compatible path is useful, but it should
not hide provider-specific options, token accounting and PDF/image limits.

## 7. Other OCR-VL / VLM Hosted Candidates

### Datalab Chandra

Datalab is a strong non-Qwen candidate because it is not just a classic OCR
engine. Its hosted API exposes document conversion and structured extraction:

- `POST /api/v1/convert` for Markdown, HTML, JSON or chunks;
- `POST /api/v1/extract` for schema-based structured extraction;
- async request/poll pattern;
- results deleted after completion window according to docs;
- conversion results can include metadata, parse quality, usage metadata and
  word-level boxes/confidence when requested;
- Chandra OCR 2 model card claims Markdown/HTML/JSON output, layout
  preservation, forms, tables, math, images/diagrams and 90+ languages.

This is close to the MVP target because it can return structured extraction
before the final LLM answer. It is also useful for auditability because source
citations/bounding boxes are part of the Datalab story.

### Together AI

Together has an official OCR quickstart that uses vision models plus structured
outputs. This is useful backup infrastructure:

- OpenAI-style client pattern;
- structured JSON examples;
- Qwen2.5-VL availability in the model catalog;
- serverless usage model.

It is still a generic VLM path unless the selected model is positioned and
tested specifically for document parsing.

### Fireworks Additional Models

Fireworks lists PaddleOCR-VL 1.6 and other vision/document-relevant models such
as RolmOCR, Qwen2.5-VL/Qwen3-VL and InternVL variants. This is a useful managed
model catalog, but the PaddleOCR-VL model page says serverless is not supported.
That makes Fireworks a managed deployment path, not the simplest immediate MVP
API.

### Model Families Not Shortlisted Yet

The following are interesting but not first-wave account choices without a clear
hosted API page and commercial terms:

- GOT-OCR / GOT-OCR2;
- InternVL OCR/document parsing variants outside a provider catalog;
- MiniCPM-V document OCR;
- Pixtral/Llama vision for document parsing;
- DeepSeek-OCR unless exposed through a simple hosted API.

They can be revisited after the first benchmark plan is stable.

## 8. Generic VLM API Backup Candidates

Generic VLM APIs are useful as a fallback/control group, not as the main OCR-VL
answer.

| Provider | Why useful | Why backup only |
| --- | --- | --- |
| Gemini API | Good image understanding, structured output docs, broad availability. | It is a general VLM API, not a dedicated OCR-VL/document parsing engine. |
| Claude API | Strong PDF/image reasoning, PDF token-cost docs, good document reasoning ergonomics. | It is not positioned as OCR-VL extraction infrastructure; schema output needs a prompt/tool contract. |
| OpenAI API | Vision models and strict structured outputs are mature; useful if account already exists. | It is a generic multimodal LLM path, not a specialized OCR-VL provider. |
| Together AI | Cheap serverless access to Qwen/Gemma vision models and structured JSON examples. | Model choice matters; it is a hosted VLM platform, not necessarily document parser. |

## 9. Baseline-Only OCR / Document AI Candidates

Keep these as secondary/control baselines:

- **Mistral OCR**: good document understanding and structured extraction story,
  but it is still not the corrected V2 main OCR-VL provider target. Use as a
  control baseline if already approved.
- **Azure Document Intelligence**: mature forms/tables/invoices baseline, but
  classic Document AI rather than OCR-VL.
- **Google Document AI**: mature enterprise Document AI, not the first OCR-VL
  shortlist path.
- **AWS Textract**: mature OCR/forms/tables baseline, not OCR-VL.
- **OCR.space**: simple OCR baseline only.

## 10. Commercial And Usage Verification

Commercial terms are not production-contract proof and are not recorded in this
GitHub markdown. Exact account terms, usage units and limits must be checked in
provider accounts or external commercial documents before benchmark execution.

Operational verification needed before any provider choice:

- confirm whether the account bills by tokens, pages, requests or deployment
  time;
- confirm image/PDF size limits and page limits;
- confirm whether failed requests are metered;
- confirm whether usage metadata is returned by the API;
- confirm retention, region and data-processing terms;
- record benchmark usage separately from customer-facing technical docs.

The most mature document parsing API candidate remains Datalab. The closest
dedicated OCR-VL paths remain Alibaba Qwen-OCR and PaddleOCR-VL official/API
providers.

## 11. Benchmark Findings

Benchmark evidence should be classified by source type:

| Evidence | Source type | Useful for | Caveat |
| --- | --- | --- | --- |
| PaddleOCR-VL model card / technical report | Vendor/model owner | Confirms 0.9B VLM document parsing, 109 languages, tables/formulas/charts and Russian/Cyrillic support. | Vendor claim; hosted provider behavior may differ. |
| PaddleOCR-VL 1.6 model page on Fireworks / HF | Provider/model owner | Confirms current hosted managed path and OmniDocBench v1.6/SOTA claims. | Fireworks path is on-demand, not serverless. |
| Datalab Chandra OCR 2 model card/docs | Vendor/model owner | Confirms Markdown/HTML/JSON, layout preservation, tables/forms/math and 90+ languages. | Need project benchmark for Russian acts/invoices. |
| Qwen OCR / Qwen-VL docs | Provider docs | Confirms dedicated OCR models, multilingual examples, table/formula/document parsing, OpenAI-compatible path and JSON output options. | Need account-level model availability, region and real token cost. |
| OmniDocBench / OCRBench v2 | Benchmark suites | Good framework for document parsing/table/multilingual evidence. | Do not translate benchmark scores into customer-document guarantees. |
| Community tests | Community signal | Useful to find hallucination, cold-start and deployment friction. | Not acceptance evidence. |

For Stage 2, the benchmark should test our document classes, not only vendor
leaderboards:

- raster scan/photo of a Russian invoice or act;
- table-heavy image;
- low-quality/skewed scan;
- simple form with key fields;
- one synthetic "should say unknown" case to catch hallucination;
- expected normalized `DocumentExtractionResultV1` shape.

## 12. Recommended Accounts To Create

1. **Alibaba Cloud Model Studio / DashScope** - https://modelstudio.alibabacloud.com/
   - Best first account for corrected OCR-VL scope.
   - Has Qwen-OCR, Qwen-VL/Qwen3-VL, OpenAI-compatible endpoint and structured
     output path.
   - Likely simple to benchmark if account usage terms are acceptable.

2. **Datalab** - https://www.datalab.to/
   - Best managed document parsing API candidate.
   - Gives Markdown/HTML/JSON conversion, schema-based extraction, bboxes and
     audit-friendly metadata.
   - Mature choice for tables/forms/layout before final LLM answer.

3. **PaddleOCR official website / AI Studio access** - https://aistudio.baidu.com/paddleocr
   - Best official PaddleOCR-VL account path.
   - Needed to verify whether the official API is easy enough for MVP.
   - If account/region friction blocks it, replace with **WaveSpeedAI Paddle
     OCR** first, then **Novita PaddleOCR-VL**.

Do not create Fireworks first unless the team accepts managed GPU deployment for
benchmarking. Do not create Azure/Google/AWS OCR accounts for the V2 main path
unless a baseline control is explicitly approved.

## 13. Recommended First Benchmark Shortlist

Main benchmark candidates:

1. **Alibaba Qwen-OCR** (`qwen3.5-ocr` or current stable `qwen-vl-ocr`)
   - Dedicated OCR-VL target, low integration friction, JSON output path.

2. **Datalab Chandra / conversion + extraction API**
   - Strong document parsing and structured extraction path; good for forms,
     tables and audit metadata.

3. **Hosted PaddleOCR-VL path**
   - First try official PaddleOCR/AI Studio API.
   - If blocked, use WaveSpeedAI or Novita as the practical hosted Paddle track.

Backup comparison:

4. **Together AI Qwen2.5-VL or similar vision model**
   - Cheap generic VLM control with structured output examples.

5. **Gemini Flash / OpenAI vision / Claude vision**
   - Use only if existing accounts/policy make them easier than dedicated
     OCR-VL providers.

Baseline-only comparison:

6. **Mistral OCR or Azure Document Intelligence**
   - Use one of them only to understand whether OCR-VL adds value over a mature
     Document AI/OCR baseline.

## 14. Implementation Notes For Adapter

Keep the adapter contract provider-neutral and evidence-preserving.

Recommended server-side abstractions:

- `DocumentExtractionRequestV1`
  - file reference or binary stream;
  - input type: `raster_image`, `pdf_page_image`, `pdf_document`;
  - task profile: `raw_text`, `table_aware`, `field_extraction`, `schema`;
  - requested output language and schema;
  - privacy/data policy marker;
  - max pages / max pixels / timeout.

- `DocumentExtractionResultV1`
  - normalized raw text;
  - Markdown when available;
  - structured JSON when available;
  - tables as arrays;
  - fields with confidence/source regions;
  - boxes/coordinates when provider returns them;
  - warnings, partial extraction flags and provider usage;
  - raw provider metadata behind retention policy.

- `DocumentExtractionErrorV1`
  - provider unavailable;
  - unsupported file;
  - file too large;
  - schema failed;
  - low confidence;
  - safety/data-policy block;
  - timeout/rate limit.

Provider-specific notes:

- Qwen adapter should support both OpenAI-compatible and DashScope-native
  request paths. Do not hide DashScope-only OCR features behind a generic client.
- Datalab adapter should support async submit/poll and schema extraction.
- Paddle adapter should classify each provider path as hosted API,
  on-demand deployment or self-hosted before any code is written.
- Generic VLM adapter should be marked backup/control, not the default OCR-VL
  provider.

OpenWebUI boundary:

- API keys stay server-side.
- Browser should not know provider details.
- The LLM should receive normalized extraction, not raw provider secrets or
  billing metadata.
- The answer must not imply production OCR correctness. Low-confidence and
  partial extraction must remain visible.

## 15. Risks And Open Questions

Open questions to verify after account creation:

- Which Alibaba region exposes `qwen3.5-ocr`, `qwen-vl-ocr-latest`,
  `qwen3-vl-flash` and `qwen3-vl-plus`?
- Does Qwen-OCR JSON mode work reliably for the target schema, or is a
  post-parse/repair step needed?
- What are actual Qwen image token counts and cost for our synthetic images?
- Does PaddleOCR official API work from our region/account without extra
  approval?
- Does the Paddle official API return JSON directly or only Markdown/text?
- Does WaveSpeedAI expose stable JSON/Markdown and useful error contracts?
- Does Novita require a persistent on-demand deployment or can it be called like
  a simple model API?
- What data retention terms apply to each provider class?
- Which providers can process Russian acts/invoices without hallucinating
  missing fields?
- What provider output should be stored, and for how long?

Risks:

- Hosted PaddleOCR-VL provider pages may describe deployment, not per-call API.
- Usage accounting can vary significantly with high-resolution images or
  verbose JSON.
- Generic VLMs can hallucinate plausible fields; benchmark must include
  negative/unknown fields.
- OCR-VL confidence and boxes are inconsistent across providers.
- Synthetic benchmark success does not approve customer-document processing.

## 16. Sources

Repo context read:

- `docs/stage2/context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md`
- `docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md`
- `docs/reports/2026-06-25/OPENWEBUI_VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.report.md`
- `docs/stage2/research/VL_OCR_PROVIDER_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/README.md`
- `README.md`

External sources checked:

- Alibaba Qwen-OCR docs:
  https://www.alibabacloud.com/help/en/model-studio/qwen-vl-ocr
- Alibaba visual understanding and billing/token docs:
  https://www.alibabacloud.com/help/en/model-studio/vision
- Alibaba structured output docs:
  https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output
- Alibaba model list / Model Studio:
  https://www.alibabacloud.com/help/en/model-studio/models
- Alibaba Model Studio console:
  https://modelstudio.alibabacloud.com/
- PaddleOCR official GitHub:
  https://github.com/PaddlePaddle/PaddleOCR
- PaddleOCR official AI Studio page:
  https://aistudio.baidu.com/paddleocr
- PaddleOCR-VL official API/service docs:
  https://ai.baidu.com/ai-doc/AISTUDIO/Dmh4onssk
- PaddleOCR official MCP docs:
  https://ai.baidu.com/ai-doc/AISTUDIO/bmfz6sbog
- PaddleOCR-VL model card:
  https://huggingface.co/PaddlePaddle/PaddleOCR-VL
- PaddleOCR-VL 1.6 model card:
  https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6
- LangChain PaddleOCR-VL loader:
  https://docs.langchain.com/oss/python/integrations/document_loaders/paddleocr_vl
- Haystack PaddleOCRVLDocumentConverter:
  https://docs.haystack.deepset.ai/docs/paddleocrvldocumentconverter
- Novita PaddleOCR-VL:
  https://novita.ai/models/model-detail/paddlepaddle-paddleocr-vl
- Fireworks PaddleOCR-VL 1.6:
  https://fireworks.ai/models/fireworks/paddleocr-vl-1-6
- WaveSpeedAI Paddle OCR:
  https://wavespeed.ai/models/wavespeed-ai/paddle-ocr
- Datalab docs:
  https://documentation.datalab.to/
- Datalab API overview:
  https://documentation.datalab.to/docs/welcome/api
- Datalab conversion API:
  https://documentation.datalab.to/docs/recipes/conversion/conversion-api-overview
- Datalab structured extraction API:
  https://documentation.datalab.to/docs/recipes/structured-extraction/api-overview
- Datalab Chandra OCR 2 model card:
  https://huggingface.co/datalab-to/chandra-ocr-2
- Datalab Chandra 2 blog:
  https://www.datalab.to/blog/chandra-2
- Together OCR quickstart:
  https://docs.together.ai/docs/quickstart-how-to-do-ocr
- Together Qwen2.5-VL:
  https://www.together.ai/models/qwen2-5-vl-72b-instruct
- Gemini image understanding:
  https://ai.google.dev/gemini-api/docs/image-understanding
- Gemini structured output:
  https://ai.google.dev/gemini-api/docs/structured-output
- Anthropic vision:
  https://platform.claude.com/docs/en/build-with-claude/vision
- Anthropic PDF support:
  https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI vision:
  https://developers.openai.com/api/docs/guides/images-vision
- OpenAI structured outputs:
  https://developers.openai.com/api/docs/guides/structured-outputs
- OmniDocBench:
  https://github.com/opendatalab/OmniDocBench
- OCRBench v2:
  https://arxiv.org/html/2501.00321v2
