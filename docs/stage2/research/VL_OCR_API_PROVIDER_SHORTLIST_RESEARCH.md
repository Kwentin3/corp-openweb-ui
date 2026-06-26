# VL OCR API Provider Shortlist Research

Checked date: 2026-06-25.

Status: research and recommendation only. No runtime proof, provider account
setup, OpenWebUI config change, production code or customer document processing
was performed.

## 1. Goal

Практический вопрос:

```text
raster image upload in OpenWebUI -> backend detects raster image ->
external VL/OCR API -> structured JSON -> LLM context -> user answer
```

Нужно выбрать 2-3 API-кандидата для первого synthetic benchmark. Это не выбор
production OCR provider and not a promise of OCR quality on real customer
documents.

## 2. MVP context

MVP-контур Stage 2 / PRD-1:

- пользователь загружает растровое изображение через OpenWebUI;
- backend классифицирует файл как raster image;
- backend вызывает внешний OCR/VL OCR API через server-side adapter;
- adapter нормализует ответ во внутренний `DocumentExtractionResultV1`;
- JSON/Markdown extraction добавляется в LLM context как evidence, not truth;
- если в extracted JSON видны sensitive data, LLM показывает warning, но не
  блокирует работу на этом этапе.

Non-goals для этой research-задачи:

- no production OCR pipeline;
- no local inference;
- no DLP or anonymization;
- no real customer documents;
- no provider account connection;
- no OpenWebUI runtime/config changes;
- no production provider decision.

## 3. What was researched

Проверены provider classes:

- Alibaba Cloud Model Studio / DashScope: Qwen-OCR, Qwen3-VL, Qwen2.5-VL,
  structured output and pricing.
- Mistral OCR / Mistral Document AI: OCR 4, OCR endpoint, Document AI,
  pricing and output structure.
- Google Gemini API: image understanding, structured output, token pricing.
- Google Cloud Document AI: Enterprise Document OCR, Layout Parser, Form
  Parser, limits and pricing.
- Azure AI Document Intelligence: Read, Layout, prebuilt models, limits,
  pricing, language support.
- PaddleOCR-VL: engine status, benchmark claims, license, hosted/API paths.
- Cheap/simple OCR APIs: OCR.space as a low-cost smoke candidate.
- Rejected/low-priority alternatives: Amazon Textract for this Russian-first
  MVP.

Repo context read:

- `docs/stage2/context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md`
- `docs/stage2/research/VL_OCR_PROVIDER_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/README.md`
- `README.md`

## 4. Candidate provider matrix

High-level fit:

| Candidate | Provider class | Main value | Main risk | MVP fit |
| --------- | -------------- | ---------- | --------- | ------- |
| Mistral OCR 4 / Document AI | Dedicated OCR/document AI API | Page-priced OCR, JSON/Markdown, bounding boxes/confidence in OCR 4, strong RAG fit | New OCR 4 release; exact limits and regional/provider behavior must be verified before benchmark | Strong |
| Alibaba Qwen-OCR / Qwen3-VL | VL OCR / VLM API | Cheap token pricing, Russian listed, tables/forms/image OCR, OpenAI-compatible endpoint | JSON/schema reliability and region/data policy need review; Qwen-OCR pricing should be verified in Model Studio console | Strong |
| Azure Document Intelligence | Enterprise document OCR/layout API | Mature API, JSON, confidence, bounding boxes, Read/Layout/prebuilt models, large file/page limits | Layout/prebuilt path is more expensive than Read; foreign cloud/data policy | Strong |
| Google Gemini API | General VLM API | Very easy image -> JSON prompt, cheap Flash/Lite token path, structured output | Not a deterministic OCR engine; confidence/page refs need custom prompt/validation | Backup |
| Google Document AI | Document OCR/parser API | Mature OCR/layout/form parsers, page-priced, JSON, processor model | Form Parser is more expensive; more setup than Gemini for a tiny MVP image path | Backup/optional |
| Hosted PaddleOCR-VL via Novita/Fireworks/PaddleOCR website | Hosted open-source OCR/VL engine | Potentially very cheap, strong public benchmark claims, 109+ language document parsing | Hosted API maturity, output contract, privacy, support and pricing need validation by live provider docs/account | Experimental |
| OCR.space | Simple OCR API | Extremely easy and cheap/free, JSON text result, Russian added in OCR Engine 2 | Weak layout/table/form guarantees; not a serious document AI baseline | Optional smoke only |
| AWS Textract | Enterprise OCR/document extraction | Mature JSON, confidence, bounding boxes, tables/forms | Russian is not in current official language list; structured extraction can be expensive | Do not use for MVP |

### 4.1 Mistral OCR 4 / Document AI capability profile

| Field | Value |
| ----- | ----- |
| Provider name | Mistral OCR 4 / Mistral Document AI |
| Provider class | Dedicated OCR/document AI API |
| Underlying engine/model, if known | `mistral-ocr-latest`, OCR 4, Document AI parameters on top of OCR |
| API endpoint / platform | Mistral API `/v1/ocr`; Mistral Studio; also available through Microsoft Foundry/Amazon SageMaker according to Mistral OCR 4 announcement |
| Input formats | Official endpoint accepts file chunks, document URLs and image URLs; Mistral OCR 4 announcement names PDF, DOC, PPT and OpenDocument; earlier docs/examples include images and PDFs |
| Raster image support | Yes, through image URL/chunk path; verify exact upload mode before benchmark |
| PDF support | Yes |
| Max file size | Commonly documented as 50 MB, but verify in current API/account before benchmark |
| Max pages | Commonly documented as 1,000 pages, but verify before benchmark |
| Russian language support | OCR 4 advertises 170 languages across language groups; Russian-specific benchmark not found in this pass |
| Tables | Yes; OCR 3/4 emphasize tables; Document AI adds schema-oriented extraction |
| Forms/invoices/acts | Yes for Document AI/custom extraction style; benchmark needed for Russian acts/invoices |
| Scans/photos | Yes |
| Poor-quality scans | Claimed improved; benchmark needed |
| Stamps/signatures | OCR 4 block classification includes signatures; do not assume legal interpretation |
| Handwriting | Claimed support in Mistral OCR/OCR 3/Document AI docs; benchmark needed |
| Layout preservation | Strong relative to text-only OCR: Markdown, blocks, bounding boxes |
| Coordinates / bounding boxes | Yes in OCR 4 via `include_blocks`; image bboxes in docs |
| Confidence / uncertainty | OCR endpoint exposes `confidence_scores_granularity` for page/word confidence; OCR 4 announcement highlights inline confidence |
| Can return JSON | Yes |
| Can follow our JSON schema | Document AI can reshape into structured JSON; still require adapter validation |
| Markdown output | Yes |
| Raw text output | Yes via normalized markdown/text |
| Batch mode | Yes; OCR 4 announcement says Batch API discount |
| Latency | Mistral claims low latency; no independent latency proof for our workload |
| Commercial terms | Check external billing docs; monetary values are not stored in repository markdown |
| Billing unit | Per page |
| 100-image planning signal | Use provider-reported usage after benchmark; no monetary estimate in GitHub |
| 1,000-image planning signal | Use provider-reported usage after benchmark; no monetary estimate in GitHub |
| Free tier / trial | Not confirmed in this pass |
| Rate limits | Account/model dependent; verify before benchmark |
| Auth model | Mistral API key, server-side only |
| Data retention / privacy notes | Enterprise/self-host option advertised for strict data residency; API retention terms must be reviewed before customer pilot |
| Region / cross-border notes | Foreign provider by default unless self-hosted/approved marketplace region is selected |
| API maturity | OCR API is mature enough for benchmark; OCR 4 is very recent |
| Docs quality | Good API docs and announcement; exact limits should be rechecked before execution |
| SDK availability | Mistral SDK/API |
| Known limitations | Benchmark claims are partly vendor-owned; exact Russian tables/acts quality unproven |
| Best use case | First structured OCR/document extraction baseline for RAG/LLM context |
| Worst use case | Production financial/legal extraction without human review |
| MVP suitability | High |
| Benchmark suitability | High |
| Production suitability later | Possible after policy, benchmark and customer pilot |
| Source links | `https://docs.mistral.ai/api/endpoint/ocr`, `https://docs.mistral.ai/studio-api/document-processing/basic_ocr`, `https://mistral.ai/news/ocr-4/`, `https://mistral.ai/pricing/` |
| Checked date | 2026-06-25 |

### 4.2 Alibaba Qwen-OCR / Qwen3-VL capability profile

| Field | Value |
| ----- | ----- |
| Provider name | Alibaba Cloud Model Studio / DashScope Qwen-OCR and Qwen3-VL |
| Provider class | VL OCR / visual understanding API |
| Underlying engine/model, if known | `qwen-vl-ocr`, `qwen-vl-ocr-latest`, `qwen3-vl-flash`, `qwen3-vl-plus`, Qwen3-VL/Qwen3.5 visual understanding family |
| API endpoint / platform | Alibaba Cloud Model Studio, DashScope/OpenAI-compatible chat completions |
| Input formats | Image URL, Base64, local path through SDK, public URL; visual docs list BMP, JPEG, PNG, TIFF, WEBP, HEIC under 4K, JPEG/PNG for 4K-8K |
| Raster image support | Yes |
| PDF support | Qwen-OCR docs mention PDF document parsing for Qwen3.5-OCR; Qwen3-VL docs mention image-based documents/image PDFs into QwenVL HTML/Markdown |
| Max file size | For image: public URL up to 20 MB for newer Qwen3.7/3.6/3.5 family, otherwise 10 MB; local path 10 MB; Base64 encoded string 10 MB |
| Max pages | Not a page-priced OCR service; multi-image limits vary by model and method; for MVP enforce one raster image per call |
| Russian language support | Model list/search docs state Qwen-VL supports 33 languages including Russian; Qwen-OCR examples include multilingual text and Russian word examples |
| Tables | Yes; Qwen-OCR docs explicitly mention table parsing |
| Forms/invoices/acts | Receipts/certificates/forms shown in docs; Russian acts/invoices require benchmark |
| Scans/photos | Yes |
| Poor-quality scans | Qwen3-VL claims robustness for blur/tilt/low light in model materials; benchmark needed |
| Stamps/signatures | Not a legal interpretation engine; visual/document parsing may detect elements, but benchmark required |
| Handwriting | Qwen-OCR/DashScope ecosystem advertises handwriting/document OCR in model listings; verify on synthetic handwriting |
| Layout preservation | QwenVL HTML/Markdown; Qwen3-VL adds Markdown parsing |
| Coordinates / bounding boxes | Visual understanding supports object/text localization; Qwen3-VL returns normalized 0-999 coordinates for localization tasks |
| Confidence / uncertainty | Not a first-class OCR confidence API in the docs reviewed; adapter should mark confidence as unavailable unless returned |
| Can return JSON | Yes by prompting; Alibaba structured-output docs support JSON object/schema modes for supported models |
| Can follow our JSON schema | Possibly via structured output for supported models; verify with exact OCR/VL model before benchmark |
| Markdown output | Yes for document parsing prompts |
| Raw text output | Yes |
| Batch mode | Multi-image inputs supported; not a page-priced batch OCR pipeline |
| Latency | Expected low for flash, higher for plus; no workload proof |
| Commercial terms | Check external Model Studio billing docs; monetary values are not stored in repository markdown |
| Billing unit | Per input/output token |
| 100-image planning signal | Use provider-reported token usage after benchmark; no monetary estimate in GitHub |
| 1,000-image planning signal | Use provider-reported token usage after benchmark; no monetary estimate in GitHub |
| Free tier / trial | Model Studio docs mention 1M free visual-understanding tokens in Singapore region for 90 days after activation |
| Rate limits | Model/account/region dependent |
| Auth model | DashScope/Model Studio API key, server-side only |
| Data retention / privacy notes | Must be reviewed under provider data policy; foreign/cross-border provider by default |
| Region / cross-border notes | Singapore, US, Germany/Frankfurt, China/Hong Kong/Beijing options appear in pricing docs; region choice matters |
| API maturity | Mature enough for benchmark; exact Qwen-OCR commercial surface should be verified |
| Docs quality | Good visual docs; Qwen-OCR docs useful; pricing/model naming is volatile |
| SDK availability | OpenAI-compatible API, DashScope SDK |
| Known limitations | Schema adherence and confidence reporting are weaker than dedicated OCR APIs; provider/model names move quickly |
| Best use case | Cheap VL OCR candidate for raster images, Russian text, tables and forms |
| Worst use case | Audit-grade extraction requiring confidence/page refs without adapter validation |
| MVP suitability | High for benchmark |
| Benchmark suitability | High |
| Production suitability later | Possible only after data policy, exact model lock and output-contract proof |
| Source links | `https://www.alibabacloud.com/help/en/model-studio/vision`, `https://www.alibabacloud.com/help/en/model-studio/qwen-vl-ocr`, `https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output`, `https://www.alibabacloud.com/help/en/model-studio/model-pricing` |
| Checked date | 2026-06-25 |

### 4.3 Azure AI Document Intelligence capability profile

| Field | Value |
| ----- | ----- |
| Provider name | Azure AI Document Intelligence / Document Intelligence in Foundry Tools |
| Provider class | Enterprise OCR/document extraction API |
| Underlying engine/model, if known | Read, Layout, prebuilt Document/Invoice/Receipt/Contract, custom extraction |
| API endpoint / platform | Azure AI Document Intelligence REST/SDK |
| Input formats | PDFs, TIFFs and images; docs mention images and forms; layout examples include JPG, PNG, BMP |
| Raster image support | Yes |
| PDF support | Yes |
| Max file size | Paid S0 tier: 500 MB; free F0: 4 MB |
| Max pages | PDFs/TIFFs: up to 2,000 pages paid; free tier processes first two pages |
| Russian language support | OCR language support includes Russian/Cyrillic for read models; verify Layout language subset before benchmark |
| Tables | Yes in Layout/prebuilt models |
| Forms/invoices/acts | Yes for prebuilt/custom; invoice/contract model exists, Russian acts require benchmark |
| Scans/photos | Yes; docs recommend clear photo/high-quality scan |
| Poor-quality scans | Better with high-quality scans; low-quality scans need benchmark and warnings |
| Stamps/signatures | Can extract signatures/selection marks/layout elements depending model; do not interpret legal meaning |
| Handwriting | Supported by OCR models for supported languages; exact Russian handwriting support must be verified |
| Layout preservation | Strong; paragraphs, roles, tables, selection marks, structure |
| Coordinates / bounding boxes | Yes, bounding regions/polygons |
| Confidence / uncertainty | Yes, confidence appears in document model responses |
| Can return JSON | Yes |
| Can follow our JSON schema | Not directly; adapter maps Azure JSON to `DocumentExtractionResultV1` |
| Markdown output | Not native primary output; adapter can create Markdown |
| Raw text output | Yes |
| Batch mode | Yes, async/batch patterns |
| Latency | Good enterprise service; benchmark needed |
| Commercial terms | Check Azure billing docs; monetary values are not stored in repository markdown |
| Billing unit | Per page |
| 100-image planning signal | Use provider-reported page usage after benchmark; no monetary estimate in GitHub |
| 1,000-image planning signal | Use provider-reported page usage after benchmark; no monetary estimate in GitHub |
| Free tier / trial | 500 pages/month free tier on pricing page |
| Rate limits | Azure resource tier/region dependent |
| Auth model | Azure key/AAD, server-side only |
| Data retention / privacy notes | Enterprise cloud terms; region and logging policy must be reviewed |
| Region / cross-border notes | Region selectable; data residency better than ad-hoc VLM APIs if configured |
| API maturity | High |
| Docs quality | High |
| SDK availability | Good SDKs |
| Known limitations | Layout/prebuilt costs more; not a VLM reasoning model; exact Russian table/form quality needs synthetic and customer pilot |
| Best use case | Deterministic OCR/layout baseline with confidence and coordinates |
| Worst use case | Cheap exploratory VLM extraction or schema reasoning |
| MVP suitability | High |
| Benchmark suitability | High |
| Production suitability later | High if customer accepts Azure provider class |
| Source links | `https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout?view=doc-intel-4.0.0`, `https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/model-overview?view=doc-intel-4.0.0`, `https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/language-support/ocr?view=doc-intel-4.0.0`, `https://azure.microsoft.com/en-us/pricing/details/document-intelligence/` |
| Checked date | 2026-06-25 |

### 4.4 Google Gemini API capability profile

| Field | Value |
| ----- | ----- |
| Provider name | Google Gemini API, Flash/Flash-Lite class |
| Provider class | General VLM API |
| Underlying engine/model, if known | Gemini Flash / Flash-Lite / Pro family; exact model ID should be selected immediately before benchmark |
| API endpoint / platform | Gemini Developer API / Vertex AI / Google AI Studio |
| Input formats | Image understanding docs list PNG, JPEG, WEBP, HEIC, HEIF |
| Raster image support | Yes |
| PDF support | Gemini can process PDFs through file/document paths depending endpoint; MVP should use raster image only |
| Max file size | Endpoint-specific; Google Agent Platform docs list 7 MB inline/direct console and 30 MB from Cloud Storage for some image features; for MVP enforce a conservative 10 MB image cap unless verified |
| Max pages | Not page-priced OCR; one raster image per call for MVP |
| Russian language support | Strong multilingual VLM likely; specific Russian OCR/table benchmark not found |
| Tables | Can reason over tables visually, but table extraction must be schema-validated |
| Forms/invoices/acts | Prompt/schema extraction possible; not deterministic OCR |
| Scans/photos | Yes |
| Poor-quality scans | Possible, but hallucination risk is higher than dedicated OCR |
| Stamps/signatures | Visual description possible; do not interpret legal meaning |
| Handwriting | Possible; benchmark needed |
| Layout preservation | Weak-to-medium unless prompt/schema captures layout |
| Coordinates / bounding boxes | Not default OCR coordinates; possible only with custom prompting/model capability |
| Confidence / uncertainty | No reliable OCR confidence by default |
| Can return JSON | Yes |
| Can follow our JSON schema | Yes, structured output supports JSON Schema subset |
| Markdown output | Yes by prompting |
| Raw text output | Yes |
| Batch mode | Batch API exists; not required for MVP |
| Latency | Usually low for Flash/Lite; benchmark needed |
| Commercial terms | Token based; check external Gemini billing docs. Monetary values are not stored in repository markdown |
| Billing unit | Per input/output token |
| 100-image planning signal | Use token counts and provider-reported usage after benchmark; no monetary estimate in GitHub |
| 1,000-image planning signal | Use token counts and provider-reported usage after benchmark; no monetary estimate in GitHub |
| Free tier / trial | Gemini API has free tier/rate limits depending model/region |
| Rate limits | Model/tier dependent |
| Auth model | Google API key or Vertex credentials, server-side only |
| Data retention / privacy notes | Paid-tier Google AI/GCP terms must be reviewed; do not use customer docs before policy |
| Region / cross-border notes | Gemini Developer API vs Vertex AI region choices differ |
| API maturity | High for VLM, not dedicated OCR |
| Docs quality | High |
| SDK availability | Good SDKs |
| Known limitations | Hallucination/schema fill risk; no native OCR confidence; page/block refs must be adapter-created |
| Best use case | Cheap VLM comparison branch: can a general VLM produce useful JSON from one raster document image? |
| Worst use case | Main production OCR baseline for regulated documents |
| MVP suitability | Medium as backup |
| Benchmark suitability | Medium-high as VLM comparator |
| Production suitability later | Only if paired with validation/human review and policy |
| Source links | `https://ai.google.dev/gemini-api/docs/image-understanding`, `https://ai.google.dev/gemini-api/docs/structured-output`, `https://ai.google.dev/gemini-api/docs/tokens`, `https://ai.google.dev/gemini-api/docs/pricing` |
| Checked date | 2026-06-25 |

### 4.5 Google Cloud Document AI capability profile

| Field | Value |
| ----- | ----- |
| Provider name | Google Cloud Document AI |
| Provider class | Enterprise document OCR/parser API |
| Underlying engine/model, if known | Enterprise Document OCR, Layout Parser, Form Parser, specialized processors |
| API endpoint / platform | Google Cloud Document AI processors |
| Input formats | Docs/pricing count images, PDF, TIFF, DOCX, XLSX, PPTX, HTML as page units; file-type docs list common images |
| Raster image support | Yes |
| PDF support | Yes |
| Max file size | Online processing max 40 MB; batch max 1 GB |
| Max pages | Processor-specific; specialized sync processors may have smaller limits; verify before benchmark |
| Russian language support | Enterprise OCR supports 200+ languages according to processor list; Russian-specific table/form quality not proven |
| Tables | Layout/Form Parser supports structures; exact output varies by processor |
| Forms/invoices/acts | Yes via Form Parser and specialized processors; Russian acts require benchmark |
| Scans/photos | Yes |
| Poor-quality scans | Needs benchmark |
| Stamps/signatures | Not a legal interpretation baseline |
| Handwriting | Enterprise Document OCR processor lists handwritten text extraction |
| Layout preservation | Good |
| Coordinates / bounding boxes | Yes in Document object/layout response |
| Confidence / uncertainty | Yes for many entities/tokens |
| Can return JSON | Yes |
| Can follow our JSON schema | Adapter maps response; custom extractor may support target fields |
| Markdown output | Not primary output |
| Raw text output | Yes |
| Batch mode | Yes |
| Latency | Good; benchmark needed |
| Commercial terms | Check Google Cloud billing docs; monetary values are not stored in repository markdown |
| Billing unit | Per page |
| 100-image planning signal | Use provider-reported page usage after benchmark; no monetary estimate in GitHub |
| 1,000-image planning signal | Use provider-reported page usage after benchmark; no monetary estimate in GitHub |
| Free tier / trial | Standard Google Cloud trial/credits may apply, not assumed |
| Rate limits | Processor/project dependent |
| Auth model | GCP service account/server-side only |
| Data retention / privacy notes | GCP terms and region must be reviewed before customer docs |
| Region / cross-border notes | Region selectable by processor; policy needed |
| API maturity | High |
| Docs quality | High |
| SDK availability | Good SDKs |
| Known limitations | More setup than Gemini; Form Parser cost is higher; not as directly OpenWebUI-native |
| Best use case | Enterprise parser comparison if Azure is already in customer/provider policy |
| Worst use case | First tiny MVP if we only need one image -> JSON quickly |
| MVP suitability | Medium |
| Benchmark suitability | Medium |
| Production suitability later | High if GCP accepted |
| Source links | `https://docs.cloud.google.com/document-ai/docs/enterprise-document-ocr`, `https://docs.cloud.google.com/document-ai/docs/processors-list`, `https://docs.cloud.google.com/document-ai/limits`, `https://cloud.google.com/document-ai/pricing` |
| Checked date | 2026-06-25 |

### 4.6 Hosted PaddleOCR-VL capability profile

| Field | Value |
| ----- | ----- |
| Provider name | PaddleOCR-VL hosted/API paths: PaddleOCR official website/API, Novita AI, Fireworks AI on-demand deployment |
| Provider class | Hosted open-source OCR/VL engine, experimental provider path |
| Underlying engine/model, if known | PaddleOCR-VL-0.9B / PaddleOCR-VL-1.5 / PaddleOCR-VL-1.6 |
| API endpoint / platform | PaddleOCR official website claims API/MCP; Novita model API/on-demand deployment; Fireworks on-demand deployment |
| Input formats | Model cards focus on image/document parsing; exact hosted API input formats vary by provider |
| Raster image support | Yes |
| PDF support | Engine supports document parsing; hosted API PDF support must be verified per provider |
| Max file size | Provider-specific; not safely known from public model cards |
| Max pages | Provider-specific; likely image/page-oriented unless wrapper handles PDFs |
| Russian language support | PaddleOCR-VL paper says 109 languages; Russian-specific examples not found in this pass |
| Tables | Yes; paper/model cards emphasize tables, formulas, charts |
| Forms/invoices/acts | Potentially, but no direct Russian acts/invoices proof found |
| Scans/photos | Yes |
| Poor-quality scans | Claimed robust in benchmark papers; real API proof needed |
| Stamps/signatures | PaddleOCR-VL 1.6 card mentions seals; signatures still not legal interpretation |
| Handwriting | Public reports mention handwritten/historical documents; benchmark needed |
| Layout preservation | Strong document parsing orientation |
| Coordinates / bounding boxes | Engine can produce structured parsing, but hosted response contract must be inspected |
| Confidence / uncertainty | Not established as stable hosted API contract |
| Can return JSON | Depends on wrapper/provider; require adapter probe before benchmark scoring |
| Can follow our JSON schema | Not assumed |
| Markdown output | Engine ecosystem supports document-to-Markdown pipelines; hosted path must be verified |
| Raw text output | Yes in principle |
| Batch mode | Provider-specific |
| Latency | Unknown for hosted; local/hosted GPU may vary widely |
| Commercial terms | Provider-specific token or GPU deployment terms; monetary values are not stored in repository markdown |
| Billing unit | Provider-specific token or GPU second/hour |
| 100-image planning signal | Use account-level API usage after benchmark; no monetary estimate in GitHub |
| 1,000-image planning signal | Use account-level API usage after benchmark; no monetary estimate in GitHub |
| Free tier / trial | Provider-specific; not assumed |
| Rate limits | Provider-specific |
| Auth model | Provider API key, server-side only |
| Data retention / privacy notes | Third-party hosted model providers require separate privacy review |
| Region / cross-border notes | Provider-specific; likely foreign/cloud path |
| API maturity | Engine is active; hosted API path is less mature than Azure/Mistral/Gemini |
| Docs quality | Good for engine/model; weaker for stable hosted business API |
| SDK availability | PaddleOCR/Transformers; hosted provider APIs vary |
| Known limitations | Not a no-effort MVP unless hosted response shape is stable; local self-host is explicitly out of this MVP |
| Best use case | Cheap experimental benchmark candidate and future offline/self-host reference |
| Worst use case | Default MVP provider before hosted API contract is proven |
| MVP suitability | Medium-low |
| Benchmark suitability | Medium as optional |
| Production suitability later | Possible as self-host/future if policy requires local inference, not current MVP |
| Source links | `https://arxiv.org/abs/2510.14528`, `https://github.com/PaddlePaddle/PaddleOCR`, `https://huggingface.co/PaddlePaddle/PaddleOCR-VL`, `https://novita.ai/models/model-detail/paddlepaddle-paddleocr-vl`, `https://fireworks.ai/models/fireworks/paddleocr-vl-1-6` |
| Checked date | 2026-06-25 |

### 4.7 OCR.space capability profile

| Field | Value |
| ----- | ----- |
| Provider name | OCR.space |
| Provider class | Simple OCR API |
| Underlying engine/model, if known | OCR.space OCR engines; engine-specific details not central to MVP |
| API endpoint / platform | OCR.space OCR API |
| Input formats | Images and multi-page PDFs |
| Raster image support | Yes |
| PDF support | Yes |
| Max file size | Free API small-file oriented; PRO PDF advertises 100 MB+; exact plan limits must be verified |
| Max pages | Plan-dependent |
| Russian language support | Russian OCR added to OCR Engine 2 in January 2025 |
| Tables | Limited; has table-related options/examples but not enterprise table parser quality |
| Forms/invoices/acts | Not a strong form/invoice extraction baseline |
| Scans/photos | Yes |
| Poor-quality scans | Has scale/orientation options; quality uncertain |
| Stamps/signatures | No reliable support |
| Handwriting | Not assumed |
| Layout preservation | Weak-to-medium with overlay coordinates |
| Coordinates / bounding boxes | Optional overlay coordinates |
| Confidence / uncertainty | Not a primary robust confidence contract for our use |
| Can return JSON | Yes |
| Can follow our JSON schema | No; adapter maps OCR.space JSON |
| Markdown output | No |
| Raw text output | Yes |
| Batch mode | Plan-dependent |
| Latency | Usually simple/fast; not verified |
| Pricing | Free API says 500 requests/day/IP; comparison page claims very low paid conversion pricing, but exact current PRO pricing should be verified |
| Pricing unit | Request/conversion/plan |
| Estimated cost for 100 images | Free under daily limit; otherwise plan-dependent |
| Estimated cost for 1,000 images | Free over multiple days or paid plan-dependent |
| Free tier / trial | Yes |
| Rate limits | Free: 500 requests/day/IP |
| Auth model | API key |
| Data retention / privacy notes | External SaaS; not approved for customer documents |
| Region / cross-border notes | External provider |
| API maturity | Mature simple OCR API |
| Docs quality | Adequate |
| SDK availability | Community wrappers |
| Known limitations | Not strong enough for layout-aware documents, tables and acts |
| Best use case | Low-cost smoke and fallback for simple printed Russian text |
| Worst use case | Main benchmark for tables/forms/scans |
| MVP suitability | Low-medium |
| Benchmark suitability | Optional simple baseline only |
| Production suitability later | Low |
| Source links | `https://ocr.space/ocrapi`, `https://ocr.space/blog/ocr-api-six-new-ocr-languages/`, `https://ocr.space/compare-ocr-software` |
| Checked date | 2026-06-25 |

## 5. Pricing comparison

Planning estimates for one raster image = one page unless provider is token
based. Token-based estimates assume compact JSON output, not verbose reasoning.
Actual benchmark must log provider-reported usage and normalized page count.

| Candidate | Billing model | 100 images signal | 1,000 images signal | Comment |
| --------- | ------------- | ------------------- | --------------------- | ------- |
| Mistral OCR 4 | Page/batch based | External billing docs only | External billing docs only | Good price/performance candidate if OCR 4 behavior matches docs |
| Mistral Document AI | Page based | External billing docs only | External billing docs only | Good if schema extraction is needed immediately |
| Azure Read | Page based | External billing docs only | External billing docs only | Mature deterministic OCR baseline |
| Azure Layout / prebuilt | Page based | External billing docs only | External billing docs only | Strong for tables/layout |
| Google Document AI OCR | Page based | External billing docs only | External billing docs only | Comparable to Azure Read |
| Google Document AI Layout | Page based | External billing docs only | External billing docs only | Comparable to Azure Layout |
| Google Document AI Form Parser | Page/features based | External billing docs only | External billing docs only | Use only if form parser is needed |
| Alibaba Qwen3-VL / Qwen-OCR | Token based | External billing docs only | External billing docs only | Potentially useful serious VL track; verify exact model usage |
| Google Gemini Flash/Lite | Token based | External billing docs only | External billing docs only | Good VLM comparator; not deterministic OCR |
| Hosted PaddleOCR-VL | Token/GPU based by provider | External billing docs only | External billing docs only | Interesting only after provider API shape is proven |
| OCR.space | Plan based | External billing docs only | External billing docs only | Too weak for serious layout benchmark |
| AWS Textract | Page/features based | External billing docs only | External billing docs only | Russian support gap makes it low priority |

Price conclusion:

- Cheapest mature OCR page baseline: Azure Read or Google Document AI OCR.
- Cheapest strong document-AI candidate: Mistral OCR 4, especially batch.
- Cheapest VL candidate: Alibaba Qwen-OCR/Qwen3-VL, if exact model/region is
  accepted.
- Cheapest experimental Paddle path: Novita-style token-hosted PaddleOCR-VL,
  but this needs API contract proof before it can enter the main MVP lane.

## 6. Benchmark findings

Useful benchmark sources and interpretation:

- OmniDocBench is a relevant document-parsing benchmark because it covers PDF
  pages, multiple document types, layouts, text blocks, tables and formulas.
  It is not a Russian business-document benchmark.
- OCRBench v2 is useful for visual-text localization/reasoning, but it is
  bilingual/text-centric rather than a direct Russian acts/invoices benchmark.
- PaddleOCR-VL papers claim strong SOTA results on public and in-house
  document parsing benchmarks, with support for many languages and complex
  elements such as text, tables, formulas and charts. These are valuable but
  still partly model-team claims.
- Mistral OCR 4 announcement reports OCR 4 leading or performing strongly on
  public/internal benchmarks and human preference evaluation, while explicitly
  warning that automated OCR benchmarks can mis-score formatting differences.
- Independent/practical community benchmarks indicate that Qwen2.5-VL and
  Mistral/Gemini-style VLM OCR can perform well on JSON extraction, but these
  are not proof for Russian invoices/acts.
- No strong public benchmark was found that directly proves Russian business
  acts, Russian invoices, stamps, signatures and dense Russian tables for all
  candidates.

Benchmark implication for Stage 2:

- Do not accept vendor leaderboard numbers as production evidence.
- First synthetic benchmark must include Russian text, table-like documents,
  low-quality scan/photo, invoice/act-like layout and sensitive-data warning.
- Score output by normalized contract fields, not by pretty LLM answer.

Suggested first benchmark classes:

1. One clean synthetic Russian text document image.
2. One synthetic Russian invoice/act image with fields.
3. One synthetic table-heavy image.
4. One skewed/low-quality scan/photo.
5. One image containing fake personal/financial/contract-sensitive values.

Minimum benchmark metrics:

- text completeness;
- table cell preservation;
- field extraction correctness;
- hallucinated fields count;
- warnings/errors present;
- confidence/page/block availability;
- adapter JSON validity;
- cost per image;
- latency;
- whether sensitive-data warning can be triggered from OCR JSON.

## 7. PaddleOCR-VL hosted/API provider findings

What PaddleOCR-VL is:

- A compact document-parsing VLM from the PaddleOCR/PaddlePaddle ecosystem.
- Public paper describes PaddleOCR-VL-0.9B as a resource-efficient
  multilingual document parser with support for 109 languages and complex
  elements such as text, tables, formulas and charts.
- PaddleOCR repo is Apache 2.0 licensed.
- Newer PaddleOCR-VL 1.5/1.6 model cards and Fireworks page indicate ongoing
  development and hosted deployment availability.

Hosted/API paths found:

- PaddleOCR official website/Hugging Face discussion claims complete API
  interfaces and MCP services are available on the PaddleOCR website.
- Novita AI exposes a PaddleOCR-VL model/API page and public model/cost
  directories list very low token-style pricing.
- Fireworks AI exposes PaddleOCR VL 1.6 as ready for on-demand deployment.
- RunPod/other GPU platforms can host the model, but that is local/self-hosted
  inference work and is explicitly outside this MVP path.

Practical conclusion:

- A hosted/API path for PaddleOCR-VL exists.
- It should not be the default MVP baseline yet, because the stable response
  schema, PDF/raster input contract, confidence support, region/privacy terms,
  cold-start behavior and real API pricing are not yet proven.
- It is worth including as an optional experimental benchmark if the team wants
  a very cheap open-source-engine comparison.
- It is not a reason to build local inference now.

## 8. Strengths and weaknesses by provider

Mistral OCR 4 / Document AI:

- Strengths: dedicated OCR, page pricing, JSON/Markdown, OCR 4 confidence and
  bounding boxes, strong RAG/document-ingestion positioning.
- Weaknesses: OCR 4 is fresh; exact limits and marketplace variants need
  verification; Russian acts/tables still unproven.

Alibaba Qwen-OCR / Qwen3-VL:

- Strengths: likely cheapest serious VL track, Russian support listed,
  OpenAI-compatible API, image -> JSON examples, QwenVL Markdown/HTML document
  parsing.
- Weaknesses: confidence is weak/unclear, structured output support must be
  verified for exact OCR/VL model, data-region policy required.

Azure Document Intelligence:

- Strengths: mature enterprise OCR/layout JSON, confidence, coordinates, large
  file/page limits, predictable pricing.
- Weaknesses: not a VLM; Layout/prebuilt costs more than Read; Russian
  acts/invoices still need benchmark.

Google Gemini API:

- Strengths: easy one-image -> JSON prompt, cheap Flash/Lite, strong structured
  output docs.
- Weaknesses: general VLM hallucination risk, no native OCR confidence/page
  extraction contract, not a document pipeline.

Google Document AI:

- Strengths: mature OCR/layout/form processors, good pricing for OCR/Layout,
  JSON and confidence.
- Weaknesses: more setup than Gemini; Form Parser is comparatively expensive;
  less attractive if Azure already covers enterprise parser baseline.

Hosted PaddleOCR-VL:

- Strengths: strong model-paper claims, open-source engine, potentially very
  low hosted cost, good table/formula/chart orientation.
- Weaknesses: hosted API contracts are not yet mature enough for default MVP;
  provider privacy and support need review.

OCR.space:

- Strengths: simple, free/cheap, JSON, Russian OCR added.
- Weaknesses: too weak for serious layout/table/document benchmark.

AWS Textract:

- Strengths: mature AWS JSON, confidence, coordinates, forms/tables.
- Weaknesses: official language list does not include Russian; forms/tables
  pricing can be high; therefore not a good first benchmark candidate.

## 9. Recommended shortlist

Recommended for first benchmark:

1. Mistral OCR 4 / Document AI - best dedicated OCR/document-AI candidate for
   image/PDF -> JSON/Markdown -> LLM context. It has page pricing, structured
   output, OCR 4 confidence/bounding-box support and a direct fit for RAG-style
   ingestion.
2. Alibaba Qwen-OCR / Qwen3-VL Flash or Plus - best cheap VL candidate and the
   most important Qwen/Alibaba path. It is valuable specifically because our MVP
   starts from a raster image and needs Russian/table/form behavior measured.
3. Azure Document Intelligence Layout plus Read - best mature deterministic
   enterprise baseline with confidence, coordinates and table/layout output.

Backup / optional:

1. Google Gemini Flash/Lite - useful VLM comparator for direct image -> JSON,
   especially if Google provider access is easier than Alibaba.
2. Hosted PaddleOCR-VL through Novita/Fireworks/PaddleOCR API - optional cheap
   open-source-engine experiment after confirming API contract and pricing.

Do not use for MVP:

1. Local self-hosted PaddleOCR-VL - useful future direction, but violates the
   current MVP constraint: no local inference.
2. AWS Textract - not first choice because Russian is missing from the current
   official language list and structured extraction can cost more.
3. OCR.space as primary provider - fine as simple text smoke, weak for
   tables/forms/layout.
4. Direct `image -> multimodal LLM -> final answer` without normalized OCR JSON
   - too hard to audit; use it only as a comparator branch.

## 10. Implementation notes for MVP adapter

Minimal backend adapter:

- `RasterDocumentExtractionAdapter` interface with one method:
  `extractRasterImage(request) -> DocumentExtractionResultV1`.
- Provider-specific adapters:
  `MistralOcrAdapter`, `QwenVlOcrAdapter`, `AzureDocumentIntelligenceAdapter`,
  optional `GeminiVisionOcrAdapter`, optional `PaddleOcrVlHostedAdapter`.
- Adapter factory selected by config/policy, but no provider key in browser.

Request envelope:

```json
{
  "request_id": "uuid",
  "document_id": "stage2-doc-id",
  "source": {
    "kind": "chat_attachment",
    "filename": "synthetic-act.png",
    "mime_type": "image/png",
    "size_bytes": 1048576
  },
  "input_class": "raster_image",
  "document_class_hint": "invoice_or_act",
  "language_hint": ["ru"],
  "extraction_profile": "ocr_table_fields_v1",
  "data_class": "synthetic",
  "provider_policy_class": "external_pilot_allowed",
  "expected_output_profile": "document_extraction_result_v1",
  "limits": {
    "max_images": 1,
    "max_size_mb": 10,
    "timeout_seconds": 60
  }
}
```

Preferred normalized JSON result:

```json
{
  "request_id": "uuid",
  "provider": "mistral_ocr_4",
  "provider_model": "mistral-ocr-latest",
  "status": "ok",
  "document_class": "invoice_or_act",
  "language": ["ru"],
  "pages": [
    {
      "page_number": 1,
      "text": "normalized page text",
      "blocks": [],
      "tables": [],
      "confidence": 0.91,
      "warnings": []
    }
  ],
  "text_blocks": [],
  "tables": [],
  "fields": [
    {
      "name": "invoice_number",
      "value": "FAKE-001",
      "confidence": 0.88,
      "page_number": 1
    }
  ],
  "sensitive_data_flags": [
    {
      "type": "personal_or_financial_like",
      "evidence": "synthetic passport-like number",
      "action": "warn_only"
    }
  ],
  "warnings": [],
  "errors": [],
  "unsupported_features": [],
  "normalized_markdown": "..."
}
```

User-visible error classes:

- `unsupported_file_type`
- `file_too_large`
- `image_resolution_too_high`
- `provider_timeout`
- `provider_rate_limited`
- `provider_error`
- `invalid_provider_response`
- `partial_extraction`
- `low_confidence`
- `table_not_reliable`
- `sensitive_data_detected_warn_only`

How to distinguish ordinary image vs document/table:

- Start with conservative MIME/extension and image metadata checks.
- Run a cheap local classifier only if already available; otherwise ask OCR
  provider for `document_class` in JSON.
- Use document-like signals: dense text, table grid, invoice/act keywords,
  many numeric fields, page-like aspect ratio, stamps/signature-like blocks.
- If classification is uncertain, still extract as `unknown_raster_document`
  and present uncertainty.

How to pass OCR JSON into LLM context:

- Pass normalized JSON/Markdown, not raw provider response.
- Include `warnings`, `confidence`, `partial_extraction` and `unsupported`
  fields before extracted text.
- Add a system/developer instruction: the LLM must not treat OCR output as
  guaranteed truth and must mention low confidence/partial extraction.

Sensitive data warning:

- Adapter or post-processor flags obvious patterns: names, phone/email, IDs,
  account-like numbers, contract numbers, invoice amounts, bank details.
- LLM receives `sensitive_data_flags`.
- UI/answer warning text for MVP: "В распознанном содержимом похожи на
  чувствительные данные. Проверьте, можно ли продолжать работу с этим файлом."
- No blocking in MVP unless data policy later says so.

Logging:

- Log: request id, provider id, model id, file MIME, file size, image dimensions,
  duration, status, error class, page/image count, token/page usage, cost
  estimate, confidence summary.
- Do not log: raw image bytes, raw extracted text, full provider response,
  secrets, customer filenames if real customer docs appear later.

MVP limits:

- one raster image per request;
- accepted MIME: `image/png`, `image/jpeg`, optionally `image/webp`;
- size cap: 10 MB before provider-specific override;
- dimension cap: resize/downscale if above provider limit; do not upscale;
- timeout: 60 seconds;
- retries: one retry on transient provider errors, no retry on policy/input
  errors;
- no PDF in first image MVP unless explicitly added as second slice;
- no real customer documents.

## 11. Risks and open questions

Risks:

- VLM providers can hallucinate missing fields.
- Tables can look plausible while cell alignment is wrong.
- Russian business documents may perform worse than English/Chinese benchmark
  samples.
- Provider pricing and model IDs are volatile.
- Confidence may be absent or not comparable across providers.
- Hosted PaddleOCR-VL providers may not expose a stable document extraction
  contract.
- Cross-border/data policy is unresolved for customer documents.

Open questions:

- Which provider classes will customer/operator allow for synthetic benchmark
  and later customer pilot?
- Should first benchmark compare page-priced OCR against token-priced VLM by
  cost per valid JSON result rather than cost per raw call?
- What exact synthetic Russian document pack should be created?
- Should `DocumentExtractionResultV1` store raw provider metadata safe subset,
  or only normalized fields?
- Which provider should be used for sensitive-data detection: adapter rules,
  LLM, or both?
- Should OCR output be persisted, transient, or attached only to the chat
  context for MVP?

## 12. What was not done

- No runtime proof.
- No provider accounts were connected.
- No API keys, `.env`, tokens, credentials or private URLs were read.
- No documents were sent to external providers.
- No real customer documents were used.
- No OpenWebUI config was changed.
- No production code was written.
- No production OCR provider was selected.
- No production OCR quality was promised.

## 13. Sources

Repo sources:

- `docs/stage2/context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md`
- `docs/stage2/research/VL_OCR_PROVIDER_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/README.md`
- `README.md`

External sources:

- Mistral OCR endpoint: https://docs.mistral.ai/api/endpoint/ocr
- Mistral OCR processor docs: https://docs.mistral.ai/studio-api/document-processing/basic_ocr
- Mistral OCR 4 announcement: https://mistral.ai/news/ocr-4/
- Mistral pricing: https://mistral.ai/pricing/
- Alibaba visual understanding docs: https://www.alibabacloud.com/help/en/model-studio/vision
- Alibaba Qwen-OCR docs: https://www.alibabacloud.com/help/en/model-studio/qwen-vl-ocr
- Alibaba structured output docs: https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output
- Alibaba model pricing: https://www.alibabacloud.com/help/en/model-studio/model-pricing
- Gemini image understanding: https://ai.google.dev/gemini-api/docs/image-understanding
- Gemini structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Gemini token counting: https://ai.google.dev/gemini-api/docs/tokens
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Google Document AI Enterprise OCR: https://docs.cloud.google.com/document-ai/docs/enterprise-document-ocr
- Google Document AI processor list: https://docs.cloud.google.com/document-ai/docs/processors-list
- Google Document AI limits: https://docs.cloud.google.com/document-ai/limits
- Google Document AI pricing: https://cloud.google.com/document-ai/pricing
- Azure Document Intelligence layout: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout?view=doc-intel-4.0.0
- Azure Document Intelligence model overview: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/model-overview?view=doc-intel-4.0.0
- Azure Document Intelligence service limits: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits?view=doc-intel-4.0.0
- Azure OCR language support: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/language-support/ocr?view=doc-intel-4.0.0
- Azure pricing: https://azure.microsoft.com/en-us/pricing/details/document-intelligence/
- PaddleOCR-VL paper: https://arxiv.org/abs/2510.14528
- PaddleOCR GitHub: https://github.com/PaddlePaddle/PaddleOCR
- PaddleOCR-VL Hugging Face: https://huggingface.co/PaddlePaddle/PaddleOCR-VL
- Novita PaddleOCR-VL page: https://novita.ai/models/model-detail/paddlepaddle-paddleocr-vl
- Fireworks PaddleOCR-VL 1.6 page: https://fireworks.ai/models/fireworks/paddleocr-vl-1-6
- OmniDocBench: https://github.com/opendatalab/OmniDocBench
- OCRBench v2: https://arxiv.org/html/2501.00321v2
- OCR.space API: https://ocr.space/ocrapi
- OCR.space Russian update: https://ocr.space/blog/ocr-api-six-new-ocr-languages/
- Amazon Textract FAQ: https://aws.amazon.com/textract/faqs/
- Amazon Textract limits: https://docs.aws.amazon.com/textract/latest/dg/limits-document.html
