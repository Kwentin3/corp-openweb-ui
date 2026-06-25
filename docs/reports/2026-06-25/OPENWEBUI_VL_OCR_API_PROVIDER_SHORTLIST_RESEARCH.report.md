# OPENWEBUI VL OCR API Provider Shortlist Research Report

Date: 2026-06-25

Status: complete for research. No runtime proof, provider setup, OpenWebUI
config change, production code, secrets access or customer document processing
was performed.

## Deliverables

- Research:
  [docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md](../../stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md)
- This closeout report:
  `docs/reports/2026-06-25/OPENWEBUI_VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.report.md`

## Repo Documents Read

- `docs/stage2/context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md`
- `docs/stage2/research/VL_OCR_PROVIDER_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/README.md`
- `README.md`

## External Sources Checked

- Mistral OCR endpoint/docs/pricing/OCR 4 announcement.
- Alibaba Cloud Model Studio visual understanding, Qwen-OCR, structured output
  and model pricing docs.
- Google Gemini image understanding, structured output, token counting and
  pricing docs.
- Google Cloud Document AI Enterprise OCR, processor list, limits and pricing.
- Azure AI Document Intelligence layout, model overview, service limits,
  language support and pricing.
- PaddleOCR-VL paper, PaddleOCR repo, Hugging Face model page, Novita and
  Fireworks hosted pages.
- OmniDocBench and OCRBench v2 benchmark sources.
- OCR.space API and Russian OCR update.
- Amazon Textract FAQ and limits for rejection rationale.

## Shortlist

Recommended for first synthetic benchmark:

1. Mistral OCR 4 / Document AI.
2. Alibaba Qwen-OCR / Qwen3-VL Flash or Plus.
3. Azure Document Intelligence Read + Layout.

Backup / optional:

1. Google Gemini Flash/Lite.
2. Hosted PaddleOCR-VL through Novita/Fireworks/PaddleOCR API, after API
   contract and pricing are verified.

## Rejected For MVP

- Local self-hosted PaddleOCR-VL: useful future path, but current MVP forbids
  local inference.
- AWS Textract: mature, but Russian is not in the current official language
  list reviewed and structured extraction can be comparatively expensive.
- OCR.space as primary provider: useful for low-cost/simple text smoke, but not
  strong enough for layout/table/form benchmark.
- Direct `image -> VLM -> final answer` without normalized OCR JSON: too hard
  to audit and not aligned with Stage 2 contract boundaries.

## PaddleOCR-VL Hosted/API Result

Hosted/API path found: yes.

Observed paths:

- PaddleOCR official website/Hugging Face discussion claims API and MCP
  interfaces.
- Novita AI exposes PaddleOCR-VL model/API pages and public model directories
  list very low token-style pricing.
- Fireworks AI exposes PaddleOCR VL 1.6 as an on-demand deployment model.

Conclusion: include only as optional experimental benchmark candidate until
stable API response shape, PDF/raster input contract, confidence support,
privacy terms, region and real account pricing are verified.

## Pricing Notes

Most interesting pricing for first benchmark:

- Azure Read: about $1.50 / 1,000 pages.
- Azure Layout/prebuilt: about $10 / 1,000 pages.
- Google Document AI Enterprise OCR: $1.50 / 1,000 pages.
- Google Document AI Layout Parser: $10 / 1,000 pages.
- Mistral OCR 4: $4 / 1,000 pages, or $2 / 1,000 pages with Batch API.
- Mistral Document AI: $5 / 1,000 pages.
- Alibaba Qwen3-VL/Qwen-OCR: token-priced and potentially very cheap; exact
  image-token/output usage must be measured in benchmark.
- Hosted PaddleOCR-VL: potentially very cheap on token-priced hosted platforms,
  but pricing is not yet a reliable MVP assumption.

## Open Questions

- Which provider classes are allowed for synthetic benchmark and later customer
  pilot?
- Which exact synthetic Russian documents should be generated first?
- Should first scoring optimize for cost per valid JSON result rather than raw
  cost per image?
- Should OCR output be persisted, transient, or attached only to LLM context?
- Which fields from raw provider metadata are safe to retain?
- Where should sensitive-data warning detection live: adapter rules, LLM, or
  both?

## Validation Notes

Planned docs-only validation:

- relative links for edited docs;
- `git diff --check`;
- staged secret-like scan before commit if committed;
- UTF-8/Cyrillic spot check;
- worktree audit.
