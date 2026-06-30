# OPENWEBUI VL OCR API Provider Shortlist Research V2 Report

Date: 2026-06-25

Status: complete for corrected research. No runtime proof, provider setup,
OpenWebUI config change, production code, secrets access, customer document
processing or external document upload was performed.

## Why Research Was Rerun

The previous provider shortlist was useful, but its scope was too broad. It
mixed classic OCR/Document AI baselines with OCR-VL/VLM document parsing
providers.

V2 narrows the question to:

```text
raster image upload -> hosted OCR-VL/VLM document API -> structured JSON/text/tables -> LLM context
```

Classic OCR/Document AI providers are kept only as optional baselines.

## Deliverables

- Corrected research:
  [docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2.md](../../stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2.md)
- This closeout report:
  `docs/reports/2026-06-25/OPENWEBUI_VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2.report.md`

## Repo Documents Read

- `docs/stage2/context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md`
- `docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md`
- `docs/reports/2026-06-25/OPENWEBUI_VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.report.md`
- `docs/stage2/research/VL_OCR_PROVIDER_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/README.md`
- `README.md`

## External Sources Checked

- Alibaba Cloud Model Studio: Qwen-OCR, Qwen-VL/Qwen3-VL, OpenAI-compatible
  mode, structured output and image-token usage docs.
- PaddleOCR-VL: official GitHub/model cards, Baidu AI Studio official API/MCP
  docs, LangChain and Haystack integrations, Novita, Fireworks, WaveSpeedAI,
  Hugging Face and serverless/deployment paths.
- Datalab: Chandra OCR 2 model card, Datalab API overview, conversion API,
  structured extraction API, commercial/changelog signals and docs index.
- Generic VLM backup: Together OCR quickstart/Qwen2.5-VL, Gemini image and
  structured output docs, Claude vision/PDF docs, OpenAI vision/structured
  output docs.
- Benchmarks: PaddleOCR-VL materials, Chandra OCR 2 materials, OmniDocBench and
  OCRBench v2.
- Baseline-only providers from V1 context: Mistral OCR, Azure Document
  Intelligence, Google Document AI, AWS Textract and OCR.space.

## Corrected Shortlist

Recommended accounts to create first:

1. Alibaba Cloud Model Studio / DashScope.
2. Datalab.
3. PaddleOCR official website / Baidu AI Studio access token.

Replacement path if PaddleOCR official account/region blocks progress:

1. WaveSpeedAI Paddle OCR.
2. Novita PaddleOCR-VL.

Recommended first synthetic benchmark:

1. Alibaba Qwen-OCR (`qwen3.5-ocr` or current stable `qwen-vl-ocr`).
2. Datalab Chandra conversion/extraction API.
3. Hosted PaddleOCR-VL path, starting with official PaddleOCR/AI Studio.

Backup:

1. Together AI Qwen2.5-VL or similar vision model.
2. Gemini / Claude / OpenAI vision only if existing account/policy makes one
   easier than a dedicated OCR-VL provider.

Baseline-only:

1. Mistral OCR.
2. Azure Document Intelligence.
3. Google Document AI.
4. AWS Textract.
5. OCR.space.

## Hosted PaddleOCR-VL Result

Hosted/API path found: yes, but not all paths are equal.

Practical classification:

- **Real hosted/official API path**: PaddleOCR official website / AI Studio
  API, with API URL and token to be copied from the official website/account.
- **Likely hosted REST API path**: WaveSpeedAI Paddle OCR; account proof still
  needed for commercial terms, schema and retention.
- **On-demand deployment path**: Novita and Fireworks; useful, but should not be
  treated as a simple per-call API until account proof confirms it.
- **Not usable as first MVP API**: Hugging Face model card only, RunPod custom
  serverless worker, self-hosted/local inference, model families without a
  proven hosted API.

## Practical MVP Answers

- Three accounts to create first: Alibaba Model Studio, Datalab, PaddleOCR
  official/AI Studio.
- Simplest likely commercial path: Alibaba Qwen-OCR or a true hosted
  PaddleOCR-VL API; exact answer requires account usage proof.
- Most mature managed document parsing path: Datalab.
- Closest to dedicated OCR-VL: Alibaba Qwen-OCR and PaddleOCR-VL official/API
  path.
- Highest operational risk: hosted PaddleOCR-VL providers that are actually
  on-demand GPU deployments rather than ready serverless APIs.
- Benchmark can be planned without local inference: yes.
- Customer pilot remains blocked by data policy, customer samples and provider
  approval.

## Documents Updated

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`

These updates route future OCR/VL OCR work to V2 first and keep V1 as a broad
historical baseline.

## Not Done

- No runtime proof.
- No provider accounts were created.
- No provider API calls were made.
- No OpenWebUI configuration changed.
- No `.env`, tokens, secrets, credentials or private URLs were read.
- No customer documents were used or uploaded.
- No production code was written.
- No production OCR quality or provider choice was promised.

## Validation Notes

Docs-only validation completed:

- `git diff --check` completed without whitespace errors.
- Relative Markdown link check for edited docs completed successfully.
- New V2 research and report files were written as UTF-8 with BOM, matching the
  previous V1 research/report artifact encoding.
- Secret-like scan over edited docs completed without findings. No stage/commit
  step was requested in this research task.
