# OpenWebUI Web Search Brave Runtime Baseline

Date: 2026-06-23

Verdict: `brave_llm_context_native_smoke_passed_with_direct_context`

## Summary

Brave `brave_llm_context` is now the working native OpenWebUI Web Search
baseline for Stage 2 smoke.

The failure was not Brave API discovery. Runtime diagnostics showed that Brave
returned search/context results and OpenWebUI could create `web-search-*`
collections. The broken stage was the follow-up vectorized retrieval path: after
embedding web-search results, source retrieval could return `0` sources, causing
the model to answer as if no online evidence was available.

The working baseline bypasses that extra stage and passes Brave LLM Context docs
directly to the LLM.

## Runtime Baseline

- Provider: Brave Search API.
- OpenWebUI engine: `brave_llm_context`.
- Result count: `3`.
- Search concurrency: `1`.
- Web loader bypass: enabled.
- Web-search embedding/retrieval bypass: enabled.
- Selected smoke model: `gpt-5.4-mini-2026-03-17`.
- Code Interpreter: removed from default features for the selected smoke model.

No provider key value was printed into this report.

## Evidence Observed

- Deployed `openwebui` container was healthy after the final config change.
- Brave LLM Context endpoint returned JSON with `grounding.generic` items.
- OpenWebUI parser returned result objects with title, link and snippet content.
- Before the final config change, OpenWebUI embedded web-search results into
  `web-search-*` collections but the subsequent source retrieval path produced
  `No sources found`.
- After enabling direct-context mode, the user confirmed the Web Search answer
  worked in the OpenWebUI UI.

## Working Config Shape

```env
ENABLE_WEB_SEARCH=true
WEB_SEARCH_ENGINE=brave_llm_context
WEB_SEARCH_RESULT_COUNT=3
WEB_SEARCH_CONCURRENT_REQUESTS=1
WEB_SEARCH_TRUST_ENV=true
BYPASS_WEB_SEARCH_WEB_LOADER=true
BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true
BRAVE_SEARCH_CONTEXT_TOKENS=8192
```

`BRAVE_SEARCH_API_KEY` must remain server-side only through Admin UI, env or an
approved secret store.

## Known Issue

`vectorized_web_search_retrieval_returns_zero_sources`

The classic path:

```text
Brave result -> OpenWebUI docs -> web-search-* vector collection
  -> retrieval sources -> LLM context
```

is not accepted as working. It should be investigated only when a product
scenario needs long-page loading, classic `brave`, SearXNG page loading, or RAG
over large fetched content.

Do not work around this by globally disabling retrieval access control. If the
path is fixed later, prefer a narrow fix around trusted `type=web_search` items
and `web-search-*` ephemeral collections.

## Remaining Gates Before Pilot Rollout

- Approved pilot group scope.
- Ordinary-user permission deny/allow proof.
- English smoke matrix.
- Forbidden-query policy checks.
- Logging and retention proof.
- Provider dashboard or native cost visibility.
- Private SearXNG comparison track, if still desired.
- Yandex privacy/data-egress review before any Yandex live smoke.
