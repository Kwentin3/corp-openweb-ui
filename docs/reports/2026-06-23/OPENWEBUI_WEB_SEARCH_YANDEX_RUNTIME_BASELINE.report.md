# OpenWebUI Yandex Web Search Runtime Baseline

Date: 2026-06-23

Scope: Stage 2 / PRD-1 / Web Search / Yandex Search API native OpenWebUI path.

Verdict: `yandex_native_search_operator_confirmed; full_smoke_evidence_pending`

## 1. Executive Summary

Yandex Search API was added through the OpenWebUI Web GUI/Admin UI, and the
owner/operator confirmed that Yandex web search works. Treat Yandex as the
working RU direct API path for controlled comparison planning.

This report is intentionally conservative: Codex did not run a fresh live
Yandex smoke in this closeout task, did not read real provider keys, and did not
inspect browser/runtime secret exposure for Yandex. The proof level is therefore
`operator_confirmed`, not a full runtime evidence package.

## 2. Scope And Non-Goals

In scope:

- record owner/operator confirmation;
- document the intended native OpenWebUI provider path;
- separate confirmed behavior from pending rollout gates.

Non-goals:

- no new live smoke;
- no production rollout approval;
- no provider config change;
- no Yandex generative answer mode baseline;
- no API key or `.env` value inspection.

## 3. Provider Path

```text
OpenWebUI native Web Search -> yandex -> Yandex Search API -> candidate set -> LLM answer
```

Yandex is a direct API provider path. It is not SearXNG-like meta-search and
does not require a sidecar, fork, or custom gateway.

## 4. Confirmed

| Item | Status |
| --- | --- |
| Yandex key added through Web GUI/Admin UI | owner/operator confirmed |
| Search path works | owner/operator confirmed |
| Role in provider matrix | working RU direct API path |
| Real keys printed in this report | no |
| Runtime changed by this closeout | no |

## 5. Not Proven In This Report

- source-card screenshot/evidence;
- candidate URL/title/snippet capture;
- logs and retention behavior;
- browser/API-key exposure check;
- ordinary-user permission allow/deny;
- pilot group behavior;
- cost visibility and budget guardrails;
- metadata-forwarding review;
- exact Yandex search mode/cost mode;
- RU/EN comparative quality matrix.

## 6. Baseline Boundaries

Use ordinary Yandex text search for baseline and comparison work. Do not treat
YandexGPT, GigaChat, or Yandex generative answer modes as part of this baseline.

Before broader rollout, owner must approve:

- allowed data classes;
- query minimization policy;
- metadata/user-info/chat-id forwarding behavior;
- cost mode and quotas;
- logging/retention policy;
- group scope and permission gates.

## 7. Recommendation

Use Yandex as Path B in the next three-path comparison:

```text
Path A: Brave direct API / brave_llm_context
Path B: Yandex direct API / yandex
Path C: Private SearXNG meta-search / searxng
```

Do not promote Yandex beyond controlled testing until the proof items above are
closed or explicitly accepted by owner.
