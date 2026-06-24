# Web Search Source Attribution Contract

Status: draft with Brave runtime baseline observation from 2026-06-23.

## Purpose

Define when a response may be called web-grounded and what source evidence must
be visible to the user.

## Grounded Answer Rule

An answer is web-grounded only if it is based on visible search sources returned
by the Web Search flow. A normal LLM answer without visible sources must not be
presented as web-grounded.

## Minimum Source Metadata

Each visible source should expose:

- title;
- URL;
- snippet or excerpt;
- provider;
- searched_at or fetched_at timestamp when available.

## Candidate Set vs Loaded Evidence

Source attribution starts at the candidate set, but candidate links are not the
same thing as evidence actually used in the final answer.

Candidate source:

- URL/title/snippet returned by Brave, Yandex, SearXNG or another search path;
- may not include full page text;
- may come from a specific upstream engine behind SearXNG.

Loaded/extracted source:

- page/content fetched from a selected candidate URL;
- normalized and chunked by OpenWebUI web loader or equivalent extraction path;
- may fail even when candidate search succeeds.

Evidence used in answer:

- the subset of candidate/loaded material that the LLM actually uses for the
  final response.

If OpenWebUI only shows candidate links but not loaded/extracted evidence, mark
that as a source-attribution limitation in the runtime report.

## Current Brave LLM Context Baseline

For `brave_llm_context`, Brave returns LLM-oriented passages and source URLs.
The current working OpenWebUI baseline passes those docs directly to the LLM:

- `BYPASS_WEB_SEARCH_WEB_LOADER=true`;
- `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true`.

This is accepted for the first Brave smoke because the provider already returns
compact LLM context. The alternative path that stores Brave results into a
`web-search-*` vector collection and retrieves sources again is not accepted
yet; runtime diagnostics showed it could return `0` sources even after search
results were found and embedded.

Keep that alternative path as a deferred known issue. It becomes required only
if source attribution must depend on loaded long pages, classic `brave`, SearXNG
page loading, or full RAG over fetched content. Until then, do not claim
vectorized Web Search retrieval is accepted.

## Source Display

- Source links/cards must be visible near the answer or in the OpenWebUI source
  panel.
- The answer should distinguish sourced facts from model reasoning.
- For freshness-sensitive answers, source recency must be inspectable through
  source dates or source pages.

## No Sources

If no sources are returned or all source fetches fail:

- show a visible no-results/no-evidence state;
- do not generate a confident grounded answer;
- allow the user to retry with a less sensitive or more specific query.

## Conflicting Sources

If sources conflict:

- mention the conflict;
- prefer primary/official sources when relevant;
- avoid a single definitive claim unless one source class clearly dominates;
- keep links visible so the user can inspect.

## Insufficient Evidence Mode

Use an explicit insufficient-evidence response when:

- sources are too old for a freshness-sensitive query;
- sources do not address the user question;
- source snippets are too thin and page fetching failed;
- provider returned only generic or unrelated results.

## Prohibited Behavior

- Do not hide that Web Search was used.
- Do not cite sources that were not returned by the search flow.
- Do not expose raw provider payloads to ordinary users.
- Do not treat snippets as proof for high-stakes legal, tax, medical or
  financial advice.
