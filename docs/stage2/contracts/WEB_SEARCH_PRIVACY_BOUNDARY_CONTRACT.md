# Web Search Privacy Boundary Contract

Status: draft for owner/security review.

## Purpose

Define what may leave OpenWebUI when native Web Search is used, and what must
remain inside the corporate boundary.

## Allowed Provider Inputs

Allowed only after provider approval:

- minimized search query derived from explicit user intent;
- selected locale/language/search type when needed;
- low result count and safe-search/category options when supported;
- provider account/API key from server-side configuration only;
- anonymous request metadata required by the provider protocol.

## Prohibited Provider Inputs

Do not send to external search providers by default:

- full raw chat transcript;
- secrets, tokens, credentials, keys, internal URLs or private hostnames;
- personal, tax, brokerage, payroll, accounting or customer-confidential data;
- uploaded document contents unless a separate data policy explicitly allows
  that provider class;
- hidden user identity, group membership or chat id unless the provider path is
  reviewed and approved;
- private system prompts or internal policies.

## Query Minimization

- Convert the user task into the shortest search query that can answer the
  stated information need.
- Prefer general terms over copied sensitive text.
- Do not include account numbers, names, document IDs, emails, phone numbers or
  internal incident identifiers.
- If minimization would destroy the meaning, block the request or ask the user
  to remove sensitive data before searching.
- Apply the same minimization rule to Brave, Yandex and SearXNG upstream
  engines.

## Provider Classes

- Foreign paid API: allowed only for approved non-sensitive queries.
- Russian cloud API: allowed only after owner/data-policy approval for the
  specific data class and cost mode.
- Private SearXNG: provides a private instance boundary and local control over
  engine selection/logs, but upstream engines, public APIs and parsed public
  pages can still receive minimized queries; do not treat it as fully private.
- Local/self-host index: preferred for internal/private content, but not part of
  the first native Web Search pilot unless separately scoped.

## Identity And Chat Metadata

- User identity forwarding is disallowed unless a provider-specific ADR accepts
  it.
- Chat id forwarding is disallowed unless a provider-specific ADR accepts it.
- Yandex and OpenWebUI `external` provider paths need special review because
  upstream code may forward user/session metadata when configured that way.
- SearXNG upstream engine exposure must be owner-approved before live queries.

## Logging And Retention

- Raw query text and raw result bodies must not be logged or retained by
  default.
- Usage events should store `query_hash`, provider, engine/mode, result count,
  latency, status and cost estimate.
- Provider error messages may be retained only after sanitization.
- Retention period for search metadata is an owner decision.

## Browser Boundary

- Provider keys never go to browser JavaScript, localStorage, sessionStorage,
  frontend config or downloadable artifacts.
- Admin UI may show masked values only.
- Runtime reports must never print provider key values, private URLs or customer
  data.

## Policy Failure Behavior

- If a query appears sensitive, return a visible policy-blocked state.
- The user-facing answer must not imply that private data was searched.
- The event stream should record `web_search_request_blocked_by_policy` without
  raw query content.
