# OpenWebUI Web Search Docs Refine: Candidate Set Model

Date: 2026-06-20

Verdict: `web_search_docs_refined_for_candidate_set_comparison`

## 1. Executive Summary

The Web Search documentation has been refined after product clarification. The
main change is conceptual: Brave, SearXNG and later Yandex are compared as
candidate discovery paths for OpenWebUI/LLM, not as interchangeable final-answer
systems.

This removes the misleading impression that private SearXNG is an index-owning
stand-in for Brave/Yandex. SearXNG is now described as a self-hosted
meta-search gateway that returns a normalized candidate set from enabled
upstream engines and public sources.

No runtime smoke was run in this refine. No secrets were read or printed.

## 2. Product Model Refinement

Candidate set:

- pre-answer list of candidate sources;
- includes URL, title, snippet/content preview, source/engine/provider,
  score/rank when available and freshness/time metadata when available;
- is not the final LLM answer;
- is not necessarily full page text.

Search/candidate discovery stage:

- finds candidate sources;
- returns URL/snippet/source metadata;
- differs by provider path.

Web loading/extraction stage:

- fetches selected URLs when enabled;
- extracts and normalizes text;
- prepares evidence chunks for LLM context.

LLM answer stage:

- synthesizes the final answer;
- shows sources when grounded;
- reports insufficient evidence when candidate/evidence quality is weak.

Comparison model:

- Path A: native OpenWebUI -> Brave `brave_llm_context` -> paid
  LLM-oriented candidate/context -> LLM answer.
- Path B: native OpenWebUI -> private SearXNG -> enabled upstream engines /
  public sources -> normalized candidate set -> OpenWebUI loader -> LLM answer.
- Path C later: native OpenWebUI -> Yandex Search API -> candidate set -> LLM
  answer, only after privacy/data-egress review.

## 3. Files Updated

- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
  - Added `Plain-Language Model`.
  - Added `Conceptual Model: Candidate Discovery vs Answer Generation`.
  - Linked the new candidate-set comparison plan.

- `docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md`
  - New plan for Brave vs SearXNG candidate set comparison.
  - Defines query matrix, capture format, scoring rubric and decision rule.

- `docs/stage2/implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md`
  - Added comparison program reference.
  - Added SearXNG candidate-set capture requirements.
  - Added shared query matrix and metrics expectations.

- `docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md`
  - Refined SearXNG as meta-search gateway, not owned search index.
  - Added upstream engine/public API/HTML parsing egress language.
  - Added limitations around no owned index, no privacy guarantee and no final
    answer generation.

- `docs/stage2/decisions/ADR-0007-web-search-provider.md`
  - Refined provider decision framing around first smoke path and comparison
    path.
  - Kept Brave as primary paid native smoke.
  - Kept SearXNG as comparison track.
  - Kept Yandex as later RU-provider after privacy/data-egress review.

- `docs/stage2/research/WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md`
  - Added SearXNG mechanism and product value section.
  - Clarified engine modules/public sources/normalized candidate set/failure
    modes.

- `docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md`
  - Added candidate source vs loaded/extracted source vs evidence used in answer.
  - Added limitation rule when OpenWebUI shows only candidate links.

- `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md`
  - Extended query minimization to Brave, Yandex and SearXNG upstream engines.
  - Clarified that SearXNG does not remove external egress risk.

- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
  - Added comparison acceptance: same query set, candidate set capture, final
    answer capture, source visibility, latency and log/privacy evidence.

- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
  - Added Brave vs SearXNG comparison query matrix and capture requirements.

- `docs/reports/2026-06-20/OPENWEBUI_SEARXNG_PRIVATE_INSTANCE.report.md`
  - Refined verdict and language around SearXNG as candidate discovery path.
  - Added candidate set refinement section.

## 4. Misleading Language Removed Or Refined

Refined away from:

- ambiguous privacy-solution framing;
- free-replacement framing;
- index-owning provider framing;
- local-only egress framing;
- final-answer-system framing;
- owned-web-index framing.

Replaced with:

- self-hosted meta-search gateway;
- private instance boundary;
- no direct paid API path, but upstream engines still receive minimized
  queries;
- candidate discovery layer;
- comparison track;
- normalized candidate set provider;
- not a full web index;
- not a privacy guarantee.

## 5. Comparison Plan Created

Created:

```text
docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md
```

The plan compares:

- candidate relevance;
- final answer groundedness;
- source quality;
- stability;
- operational fit;
- privacy/egress;
- logs;
- latency;
- cost/ops.

The output template is:

```text
docs/reports/YYYY-MM-DD/OPENWEBUI_WEB_SEARCH_BRAVE_VS_SEARXNG_COMPARISON.report.md
```

Expected final recommendation values:

- `brave_primary_searxng_secondary`
- `searxng_viable_self_host_meta_search_alternative`
- `searxng_not_viable_for_pilot`
- `need_more_runtime_evidence`
- `yandex_should_be_evaluated_next`

## 6. Remaining Runtime Work

- Brave `brave_llm_context` smoke using owner-provided account/API key through
  approved server-side path.
- Private SearXNG runtime smoke on Linux-container Docker host with Compose.
- Brave vs SearXNG comparison report using the same query matrix.
- Yandex privacy/data-egress review before any live Yandex smoke.

Blocked/not done:

- no Brave runtime smoke in this refine;
- no SearXNG runtime smoke in this refine;
- no Yandex runtime smoke;
- no provider credentials read or printed.

## 7. Readiness Check

Ready:

- docs no longer present SearXNG as an index-owning substitute for
  Brave/Yandex;
- SearXNG is described as self-hosted meta-search gateway;
- candidate set model is documented;
- Brave vs SearXNG comparison plan exists;
- acceptance/test-data require same query matrix;
- privacy docs explicitly say upstream engines can receive minimized queries;
- Brave remains primary first smoke;
- SearXNG remains comparison track;
- Yandex remains later RU-provider after privacy/data-egress review.

Verification run:

- misleading-language scan: no matches for replacement/privacy/owned-index
  framing patterns;
- positive model scan: Brave primary, SearXNG comparison, candidate set and
  Yandex-later language present in Stage 2 docs/reports;
- YAML parse: `compose/searxng.private.compose.yml`,
  `compose/searxng.debug.compose.yml` and `deploy/searxng/settings.yml` parse
  as dictionaries;
- `git diff --check`: passed; Git reported only LF-to-CRLF working-copy
  warnings;
- secret-pattern scan: only placeholders, environment references and
  documented secret-generation commands were found.

Still required:

- owner review of refined product model;
- runtime evidence before promoting any provider path.
