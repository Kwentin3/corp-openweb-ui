# Web Search Candidate Set Comparison Plan

Status: ready for runtime smoke after owner/runtime access.

## 1. Purpose

Compare Brave `brave_llm_context` and private SearXNG as two ways to generate a
candidate set for OpenWebUI/LLM. This is not a generic search-engine benchmark
and not a claim that SearXNG can stand in for Brave, Yandex or any owned search
index.

## 2. Product Model

Web Search has three stages:

1. Search/candidate discovery returns a candidate set.
2. OpenWebUI web loader/extraction prepares evidence chunks from selected
   candidate URLs when that path is enabled.
3. The LLM synthesizes the final answer and displays sources or says evidence
   is insufficient.

Candidate set means the pre-answer list of source candidates:

- URL;
- title;
- snippet or content preview;
- source engine/provider;
- score/rank when available;
- freshness/time metadata when available.

The candidate set is not the final answer and not necessarily the full page
text.

## 3. Scope

Compare:

- candidate set quality;
- final answer quality;
- source visibility;
- latency;
- stability;
- cost and ops effort;
- privacy/egress behavior;
- logging behavior;
- permissions;
- failure modes.

## 4. Non-Goals

- no universal search benchmark;
- no SEO-quality benchmark;
- no production rollout;
- no sidecar;
- no OpenWebUI fork;
- no public SearXNG instance acceptance;
- no sensitive/customer data in live queries;
- no claim that SearXNG owns a full web index.

## 5. Test Paths

Path A:

```text
OpenWebUI -> Brave brave_llm_context -> candidate/context -> LLM answer
```

Path B:

```text
OpenWebUI -> private SearXNG -> enabled upstream engines/public sources
  -> normalized candidate set -> OpenWebUI web loader -> LLM answer
```

Optional later path:

```text
OpenWebUI -> Yandex Search API -> candidate set -> LLM answer
```

Yandex is not part of the first comparison until privacy/data-egress review is
approved.

## 6. Query Set

Use the same live-safe queries for Brave and SearXNG.

RU ordinary:

- `актуальные ставки НДС в России 2026`
- `изменения в 6-НДФЛ 2026`
- `OpenWebUI SearXNG настройка`
- `лучшие практики корпоративного AI чата`
- `как работает Brave Search API`

EN ordinary:

- `OpenWebUI SearXNG web search setup`
- `Brave Search API OpenWebUI brave_llm_context`
- `SearXNG JSON API settings`

Freshness-sensitive:

- current OpenWebUI latest stable release;
- current Brave Search API pricing;
- current Yandex Search API pricing.

Conflicting-source:

- one query where official docs and blogs may differ;
- one query where sources likely disagree.

No-sufficient-evidence:

- obscure/internal-like topic with no public source;
- intentionally underspecified query.

Forbidden examples:

- API keys;
- private customer data;
- broker/tax/financial document content;
- personal data.

Forbidden examples are policy tests, not live external search queries unless a
safe mock or policy gate is used.

## 7. Capture Format

For each query/provider:

- provider/path;
- query text or query hash if sensitive;
- timestamp;
- result count;
- candidate URL list;
- title/snippet;
- source domain;
- whether source is official, primary, secondary or noisy;
- whether page loading was used;
- whether final answer cited sources;
- search latency;
- page load/extraction latency;
- total answer latency;
- timeout/rate-limit/CAPTCHA/no-results/source-load errors;
- whether raw query appeared in logs;
- whether raw result appeared in logs;
- whether provider key or internal endpoint leaked to browser;
- Brave request cost estimate;
- SearXNG infra/ops note;
- human evaluator notes.

## 8. Scoring Rubric

Use a simple 0-3 scale.

Candidate relevance:

- 0: no useful candidates;
- 1: mostly noisy;
- 2: mixed but usable;
- 3: strong/primary sources.

Answer groundedness:

- 0: hallucinated or unsupported;
- 1: weak support;
- 2: acceptable;
- 3: clearly grounded with inspectable sources.

Source quality:

- 0: no sources;
- 1: blogs/noisy;
- 2: mixed;
- 3: official/primary/reputable.

Stability:

- 0: fails often;
- 1: unstable;
- 2: acceptable;
- 3: stable.

Operational fit:

- 0: too costly or fragile;
- 1: heavy ops;
- 2: acceptable;
- 3: simple.

## 9. Decision Rule

Brave remains primary if:

- SearXNG quality is weaker or unstable;
- SearXNG has CAPTCHA/rate-limit issues;
- SearXNG ops burden outweighs no-direct-paid-API benefit;
- Brave source visibility and latency are clearly better.

SearXNG can become a serious comparison alternative if:

- candidate relevance is close to Brave;
- RU/EN quality is acceptable;
- latency is acceptable;
- logs are safe;
- source cards are visible;
- upstream leakage is owner-approved;
- ops cost is acceptable.

SearXNG should not become primary if:

- it only proxies Brave API;
- public instances are required;
- upstream engines are unstable;
- it cannot return useful JSON consistently;
- source attribution is poor;
- raw sensitive queries appear in logs.

## 10. Output Report Template

After runtime comparison, produce:

```text
docs/reports/YYYY-MM-DD/OPENWEBUI_WEB_SEARCH_BRAVE_VS_SEARXNG_COMPARISON.report.md
```

The report must include:

- executive summary;
- tested providers;
- query matrix;
- per-query comparison table;
- candidate quality scores;
- answer quality scores;
- source visibility;
- latency;
- logging/privacy findings;
- cost/ops findings;
- final recommendation.

Allowed final recommendations:

- `brave_primary_searxng_secondary`
- `searxng_viable_self_host_meta_search_alternative`
- `searxng_not_viable_for_pilot`
- `need_more_runtime_evidence`
- `yandex_should_be_evaluated_next`
