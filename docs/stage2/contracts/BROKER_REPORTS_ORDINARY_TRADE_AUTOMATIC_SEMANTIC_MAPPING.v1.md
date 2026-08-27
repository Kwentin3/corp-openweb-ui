# Ordinary Trade Automatic Semantic Mapping v1

Status: `CURRENT AUTHORITY`

Updated: 2026-08-27

## Scope

The active `ordinary_trade_automatic_semantic_mapping_v1` route keeps qualified
exact mappings as a zero-call fast path. An unknown Canonical table schema is
not rejected merely because it is absent from that registry: one strict source
adapter may propose the table disposition, column roles, side literals and
consumer-required amount/currency bindings.

The model receives only bounded immutable Canonical table context. It does not
author literals, source references, Canonical changes, facts or tax meaning.
Broker, year and filename routing, fuzzy matching, retry, best-of-N, output
repair and fallback to historical Gate 3 are forbidden.

## Case lifecycle

`OrdinaryTradeMappingCaseFactory.create` owns an append-only private case bound
to the exact active Canonical identity and authenticated user, case, chat and
workspace. Revisions are deterministic; stale or concurrent answers fail
closed. A clarification is resumed in that same case. Free text is interpreted
only against the current option identifiers by a strict Human Adapter.

A candidate never becomes executable implicitly. Native OpenWebUI confirmation
must append the confirmed understanding. Only `COMPLETE` exposes mapping v3 and
`broker_reports_ordinary_trade_case_mapping_qualification_v1`; the receipt
prohibits global reuse and seals the exact model response, execution metadata,
confirmed understanding and Canonical/table scope.

## Completeness and terminals

Every Canonical table receives exactly one disposition:

- `SECURITY_TRADES` requires a complete validated mapping;
- `NO_NAMED_CONSUMER` retains literal observations and provenance but emits no
  Fact v2;
- `UNSUPPORTED_FINANCIAL_MEANING` stops with a typed owner blocker;
- ambiguity produces one bounded clarification and no mapping admission.

Until all relevant tables are confirmed and complete, Gate 4 publishes no
partial Fact v2. Provider failure, invalid structured output, source-context
limit, unsupported meaning and specialist-review need remain distinct typed
states with no late mutation or silent repair.

## Release boundary

Package/bundle parity, tenant isolation, concurrency, adversarial inputs and the
saved corpus matrix are required before release. The real OpenWebUI clean-room
proof runs only after the dependency branch is transferred onto fresh
`origin/main`; it must prove one unknown schema, one ambiguity dialogue, the
known-schema zero-call fast path and unchanged Canonical identity.
