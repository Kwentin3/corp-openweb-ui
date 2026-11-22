# Web Search defaults

18 November 2026: native search defaults and useful retrieval accepted in
ordinary chat and Realtime. A read-only settings/image spot check on 22 November
confirmed the fields below; it did not repeat browser or provider acceptance.

## Configuration owner and scope

Web Search was enabled in Default Features for all fourteen visible workspace
models in the 18 November production catalog. The native workspace model
registry owns this configuration: `meta.defaultFeatureIds` includes
`web_search`, and `meta.capabilities.web_search=true`. The three Office profiles
also needed `meta.builtinTools.web_search=true` because their customized tool
categories disabled it. Other defaults, system prompts, tools, knowledge,
ownership, grants and active flags were preserved. Inactive records, the hidden
budget service and a legacy record absent from the served catalog were excluded.

The 22 November spot check confirmed these search fields on all fourteen saved,
active baseline records, including the three explicit Builtin Tools categories.
The live served catalog was not queried again; this is not a claim about every
model that might be added later or functional acceptance across all models.

New ordinary chats and Realtime handoff use the selected chat model's enabled
features. Native function calling decides whether to search; the default does
not force an external query for every message. Users can disable search in the
chat subject to existing permissions. Refresh and start a new chat to load model
defaults; existing open chat controls may retain their previous state.

The existing SearXNG connection remains the search owner. Enabling model defaults
needed no core patch, new service, image build or restart. The later retrieval
repair recreated only SearXNG; Realtime rights and dictation were preserved.

## Adding and updating models

In native model settings enable Web Search capability and **Default Features →
Web Search**. If Builtin Tools categories are customized, enable Web Search there
too. Preserve other model settings and grants. Per-model defaults are not
automatically inherited by new models; include this check during onboarding.

## Retrieval repair and image identity

Before the repair, all fourteen model selections showed active Web Search in
fresh browser chats, but the tested Realtime handoff's `search_web` calls returned
empty results. A visible control therefore did not establish useful retrieval.

The query URL explicitly selects `duckduckgo web`. Its `disabled: true` means
disabled by default, not unavailable to explicit `engines=` selection; the flag
was not the proven cause. The old SearXNG `2026.6.22-952896d29` returned an empty
JSON result. Bounded upstream checks observed DuckDuckGo HTTP 202/non-JSON
challenge, Brave HTTP 429 and Startpage CAPTCHA. The existing proxy did not
resolve those responses.

Official SearXNG `2026.11.18-b867c56a5` includes native DuckDuckGo challenge
handling and browser impersonation. An isolated probe of the exact candidate
image returned ten useful results for each of two representative queries before
the production change. The existing Compose owner then recreated only SearXNG.
Its JSON route returned useful results; unrelated container IDs and search
settings were preserved. No new provider, proxy, service or core patch was added.

The accepted Linux/amd64 image is pinned in `.env.example` and the Compose
fallback to
`docker.io/searxng/searxng@sha256:e7b769bbf99bbef7c93c1aee2299c085e3f18e3da046fdc59148c0ff1eef6869`.
Upstream revision: `b867c56a5668966ef4be8097f1b559bdc2841743`.

The protected deployment environment owns `SEARXNG_IMAGE`; the source Compose
files are `compose/openwebui.compose.yml` and
`compose/searxng.private.compose.yml`, project `compose`. Exact host locations
belong to the private operator inventory. The 22 November read-only spot check
confirmed the same image, selector and Compose owner, healthy with zero restarts.
This source reconciliation did not restart or reconfigure any service.

## Product acceptance on 18 November

- Ordinary `gpt-6-luna` chat passed `web_search=true`, received five useful
  `search_web` results, fetched three source pages with native `fetch_url`, and
  answered the Sochi forecast with citations and source update time. Values were
  compared with the fetched text.
- Full `gpt-realtime-2.1` used a real browser and synthetic Russian microphone
  audio, delegated to that chat model with `web_search=true`, and spoke the final
  result. This covered native handoff and speech, beyond a WebSocket handshake.
- A search snippet lagged its source page. A supplementary voice request opened
  the page with `fetch_url`; the spoken values matched the checked page. For
  time-sensitive facts, open the source rather than relying only on a snippet.
  The citation remained in chat, but the voice model spoke a generic source label;
  exact spoken source naming remains model-dependent.

This acceptance covers the tested scenarios, not every model's search behavior
or physical microphone/mobile compatibility. No special weather API or new prompt
was introduced. OpenWebUI was not restarted during the retrieval repair. Owned
synthetic chats, native tasks, temporary candidate containers and token files were
removed; recovery assets were intentionally retained.

## Recovery and retained evidence

Protected before/expected model snapshots, native version history and operator
receipts remain under the `web-search-defaults-20261118` task identifier. Restore
only the touched search fields through the native model editor/API after checking
later edits; never replace whole model records over unrelated changes.

The `search-repair-20261118` operator inventory holds protected image/Compose/env
snapshots and the scoped `rollout.py` helper. Exact paths and credentials stay
outside the repository. Retained local evidence archives for both task identifiers
were checked against their recorded SHA-256 on 22 November. Known server recovery
snapshots/helpers also exist. Keep these assets; loose helpers and temporary
containers are not the recovery source of truth.

The previous exact image is retained for recovery:
`searxng/searxng@sha256:3f52dca114d96af03ab68c666614571395e1c1d9ac7b4eecf7f88ee5072a0942`.
From the protected operator directory, `python3 rollout.py rollback-plan` checks
the current image/settings and renders a change to only the image selector,
without restarting services. This dry run passed on 18 November; actual rollback
to the known-broken old engine was not executed.

An explicitly authorized `python3 rollout.py rollback` checks drift and rendered
Compose, restores only the selector and recreates only SearXNG. Preserve other
environment entries and services. Do not override a drift rejection. Check health
and useful native JSON/product results after rollback; the old image previously
returned empty results under the observed external conditions.

## References

- [Official native search setup](https://docs.openwebui.com/features/chat-conversations/web-search/agentic-search/#setup)
- [SearXNG disabled-engine semantics](https://docs.searxng.org/admin/settings/settings_engines.html#disabled)
- [Accepted DuckDuckGo implementation](https://github.com/searxng/searxng/blob/b867c56a5668966ef4be8097f1b559bdc2841743/searx/engines/duckduckgo_web.py)
- [Realtime operation and access](realtime-voice.md)
