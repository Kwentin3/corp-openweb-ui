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

A candidate never becomes executable implicitly. Every clarification option
contains a validator-checked, machine-applicable decision bound to the exact
table/header and column, literal, binding or disposition. Native OpenWebUI
confirmation must append that decision and its digest. A final mapping that
does not satisfy every confirmed decision fails closed. Only `COMPLETE` exposes mapping v3 and
`broker_reports_ordinary_trade_case_mapping_qualification_v1`; the receipt
prohibits global reuse and seals the exact model response, execution metadata,
confirmed decision and Canonical/table scope.

The model-facing package uses opaque table ordinals, omits Canonical/case
identities and hashes, and bounds source rows to the minimum mapping sample.
Code adds a bounded distinct-value surface for every column from the full
Canonical so rare side literals below the row sample remain addressable.
The answer interpreter receives question text and option labels/IDs only; the
machine decisions remain code-owned case state.

Model-authored option and interpretation wording is never the public meaning of
a confirmation. Code binds every option to the validated decision and separates
the exact header/literal surface as untrusted source data. The presentation LLM
may author one natural subject question only from the current opaque question,
complete option-ref set and code-owned descriptions of the validated column,
financial role or binding. It receives no source-derived title, header or cell
text. Runtime separately renders that text as quoted evidence. Native
confirmation remains an exact code-owned rendering of the selected validated
decision. Therefore displayed column/role/binding and applied decision cannot
diverge.

The product composition publishes that bounded public surface as one
`MAPPING_CLARIFICATION` action. The representation-only public-dialogue adapter
projects an opaque current-question ref, opaque option refs, code-owned option
meaning into a strict communication brief; it never copies tagged source data,
raw mapping state or machine decisions into the presentation prompt. The model
returns one natural question plus the exact existing bindings. Runtime checks
the complete binding, one-question speech-act shape and exact presence of every
code-owned safe option description; it does not interpret source or human
wording with a regex, keyword or lexical semantic filter. Tagged source data is
validated only for exact structure and size, then appended by runtime as quoted
evidence. Invalid output falls back to the same bound question and evidence. A
pending candidate instead projects the exact code-owned confirmation with only
`Да` / `Нет` and does not require a presentation-model call. Internal role
codes, mapping vocabulary and Fact contract names are forbidden on both public
paths.

## Completeness and terminals

Every Canonical table receives exactly one disposition:

- `SECURITY_TRADES` requires a complete validated mapping;
- `NO_NAMED_CONSUMER` retains literal observations and provenance but emits no
  Fact v2 only after an exact machine-applicable table-disposition decision was
  explicitly confirmed; model output alone stops for specialist review;
- `UNSUPPORTED_FINANCIAL_MEANING` stops with a typed owner blocker;
- ambiguity produces one bounded clarification and no mapping admission.

Until all relevant tables are confirmed and complete, Gate 4 publishes no
partial Fact v2. Provider failure, invalid structured output, source-context
limit, unsupported meaning and specialist-review need remain distinct typed
states with no late mutation or silent repair.

`COMPLETE` additionally requires exact coverage of every literal in the chosen
side column from the full Canonical and a deterministic compiler dry-run with
zero `RELEVANT_UNMAPPED` observations. Sample truncation cannot weaken this
full-source check; incomplete coverage stops in the mapping case before any
qualified material is persisted.

## Release boundary

Package/bundle parity, tenant isolation, concurrency, adversarial inputs and the
saved corpus matrix are required before release. The real OpenWebUI clean-room
proof runs only after the dependency branch is transferred onto fresh
`origin/main`; it must prove one unknown schema, one ambiguity dialogue, the
known-schema zero-call fast path and unchanged Canonical identity.
