# Ordinary Trade Automatic Semantic Mapping v1

Status: `CURRENT AUTHORITY`

Updated: 2026-08-31

## Scope

The active `ordinary_trade_automatic_semantic_mapping_v1` route keeps qualified
exact mappings as a zero-call fast path. Only table nodes not covered by that
frozen path enter the model package. An unknown Canonical table schema is
not rejected merely because it is absent from that registry: one strict source
adapter may propose the table disposition, column roles, side literals and
consumer-required amount/currency bindings.

The proposal model receives one code-built semantic view for every selected
Canonical table: its untrusted `content.title`, flattened `content.header`,
ordered `content.rows`, full row count and bounded per-column distinct values.
The same serialized case bytes are sent unchanged to a separate critic model.
Only the critic-reviewed response may reach validation and compilation. Neither
model authors literals, source references, Canonical changes, facts or tax meaning.
Broker, year and filename routing, fuzzy matching, retry, best-of-N, output
repair and fallback to historical Gate 3 are forbidden.

For source-bound tables the runtime, not either model, binds the flattened
header to `table_header_binding.bound_header_row_count`. A response cannot
select a physical header row. The compiler matches that exact Canonical header
view, then reads values only from immutable physical `content.cells` below the
bound header count. Canonical remains the structure owner and the compiler
remains the sole runtime-record producer.

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
confirmed decision, semantic-evidence digest and Canonical/table scope. New
revisions use `broker_reports_ordinary_trade_mapping_case_v3`. Existing v2 case
artifacts remain readable under their frozen v2 validator. An in-progress v2
case continues as a v3 successor with the v2 integrity digest as predecessor;
an already-complete v2 case is compatibility material and is not represented as
having received the new independent critic retroactively.

Execution preserves that distinction: frozen mappings remain schema-scoped;
case mappings remain exact-node-scoped. Two table nodes with the same structure
are independent source containers. A confirmed case decision for each node may
execute without inferred continuation, while a case mapping that overlaps a
frozen mapping on the same node fails closed as an authority conflict.

The model-facing package uses opaque table ordinals and omits Canonical/case
identities and hashes. It carries Canonical title, flattened header and ordered
body rows; long row surfaces and high-cardinality distinct-value surfaces are
explicitly marked as truncated. `NO_NAMED_CONSUMER` cannot be admitted from a
truncated surface, even after critic approval. Code adds a bounded
distinct-value surface for every column from the full Canonical so rare side
literals below the row sample remain addressable when that surface is complete.
The answer interpreter receives question text and option labels/IDs only; the
machine decisions remain code-owned case state.

Model-authored option and interpretation wording is never the public meaning of
a confirmation. Code binds every option to the validated decision and separates
the exact header/literal surface as untrusted source data. The presentation LLM
authors the current subject turn by selecting one closed natural-question plan
from the current opaque question, complete option-ref set and code-owned
descriptions of the validated column, financial role or binding. It receives no
source-derived title, header or cell text and returns no free-form mapping
wording. Runtime renders the chosen plan and separately appends source text as
quoted evidence. Native
confirmation remains an exact code-owned rendering of the selected validated
decision. Therefore displayed column/role/binding and applied decision cannot
diverge.

The product composition publishes that bounded public surface as one
`MAPPING_CLARIFICATION` action. The representation-only public-dialogue adapter
projects an opaque current-question ref, opaque option refs, code-owned option
meaning into a strict communication brief; it never copies tagged source data,
raw mapping state or machine decisions into the presentation prompt. The model
returns one allowed question-plan ref plus the exact existing bindings; the
mapping-turn response schema exposes only those plan refs. Runtime checks the
complete binding and plan membership, then composes exactly one
question from every code-owned safe option description. No model-authored free
text enters this mapping speech act, and runtime does not interpret source or
human wording with a regex, keyword or lexical semantic filter. Tagged source
data is validated only for exact structure and size, then appended by runtime as
quoted evidence. Invalid output falls back to the same bound question and
evidence. A
pending candidate instead projects the exact code-owned confirmation with only
`Да` / `Нет` and does not require a presentation-model call. Internal role
codes, mapping vocabulary and Fact contract names are forbidden on both public
paths.

## Completeness and terminals

Every Canonical table receives exactly one disposition:

- `SECURITY_TRADES` requires a complete validated mapping;
- `NO_NAMED_CONSUMER` retains literal observations and provenance but emits no
  Fact v2 only after the independent critic approves the exact
  machine-applicable table-disposition decision on the same complete semantic
  evidence; truncated row or distinct-value evidence fails closed;
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

The current independent-critic path is two calls for an unknown schema and zero
calls for a frozen exact mapping. Proposal and critic receive the same semantic
case digest. They are independent clients; using one client object for both
roles fails closed. Provider or validator failure publishes zero facts.

Within a qualified trade table, display-only text rows may be retained without
blocking. That terminal requires every non-empty mapped field to be display or
reference text with no standalone transaction/monetary consumer. A row with any
non-empty mapped date, side, quantity, price, currency, amount, commission,
accrued-interest or settlement value remains `RELEVANT_UNMAPPED`; it emits zero
Fact v2 until the exact row contract is complete.

## Release boundary

Package/bundle parity, tenant isolation, concurrency, adversarial inputs and the
saved corpus matrix are required before release. The real OpenWebUI clean-room
proof runs only after the dependency branch is transferred onto fresh
`origin/main`; it must prove one unknown schema, one ambiguity dialogue, the
known-schema zero-call fast path and unchanged Canonical identity.
