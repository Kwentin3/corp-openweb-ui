# Broker Reports Gate 5 Deterministic Source-Fact Consumption v0

Status: `CURRENT SUPPORTING CONTRACT`

Goals: `G5.40E`, additive `G5.40F` available-evidence assembly

Date: 2026-08-13

## Boundary

`Gate5DeterministicSourceFactConsumptionRuntimeFactory.create` is the sole
owner of this proof boundary. It composes
`Gate4FinancialCaseRuntimeFactory.create` and the existing trusted methodology
authority. It reads complete `Gate4FinancialCaseFactV2` objects only; it does
not read source bytes, Canonical, Gate 3, SQL, or a provider.

The proof-only published methodology is
`ru-ndfl-securities-source-fact-consumption-proof@2026.5-experimental`. Its
package resource and SHA-256 pin are owned by the existing trusted methodology
authority.

## Consumer-first inputs

For the bounded 2025 resident, organized-market, outside-IIS securities slice,
the existing declaration Tax Model requires:

| Consumer meaning | Source-fact requirement | Deterministic rule |
| --- | --- | --- |
| gross income | complete `SECURITY_DISPOSAL` date, asset, quantity, amount, currency | absolute source amount |
| acquisition cost | complete prior `SECURITY_PURCHASE` facts with the same asset and currency | date-ordered FIFO; proportional amount by consumed quantity |
| transaction expense | `TRANSACTION_CHARGE` on the same explicit canonical table row as the disposal | sum same-source-row amounts only |

No purchase-to-sale event, relation, membership edge, or reconciled operation
is created or persisted. Same-date lots with different unit costs fail closed
when a partial consumption makes their unknown order material. Non-minor-unit
allocation and insufficient acquisition quantity also fail closed.

Table-row identity is structural evidence, not an inferred financial-event
edge. `table_row` and `table_cell` targets may match only when their canonical
binding, table node, and zero-based row are identical. A shared page, date,
asset, nearby position, literal value, or coarse table-node target is never
sufficient.

An ordinary text-node match is also insufficient. A future non-table route
would require an explicit source-authored atomicity contract; node equality
alone does not prove transaction identity.

`Gate5SecuritiesDisposalTaxModelRuntime.run_from_current_source_facts` invokes
the consumer owned by its factory, validates the result and delegates unchanged
Tax Model and declaration projection behavior to their existing owners. It
accepts no caller-supplied fact-consumption payload and does not rediscover or
rewrite facts.

## Source granularity

Commission detail (`COMMISSION` and source-authored `TRANSACTION_CHARGE`) and
`COMMISSION_TOTAL` remain independent assertion sets. `TAX_WITHHELD` and
`TAX_WITHHELD_TOTAL` follow the same rule. Detail, aggregate, and hybrid modes
retain exact facts and provenance; no comparison, repair, allocation, or
reconciliation is performed.

`Gate5DeterministicSourceFactConsumptionRuntime.assess` is the read-only
sufficiency boundary for mixed real-source cases. It preserves both assertion
sets and reports incomplete or invalid purchase/disposal inputs as
`SOURCE_EVIDENCE_INSUFFICIENT`. It does not drop those inputs to make FIFO
appear complete.

`Gate5DeterministicSourceFactConsumptionRuntime.assemble_available` is the
additive G5.40F read-only boundary. It partitions only by exact methodology
inputs `(asset, currency)`, applies FIFO independently inside each group, keeps
every source fact, and returns exact group/fact blockers. A failed group cannot
erase a successfully calculated independent group. Purchase-only groups remain
`NOT_ACTIVATED_FOR_SUPPLIED_CASE`; they are not forced into a disposal event.

Missing acquisition quantity in the current Gate 4 set is an
`EVIDENCE_HORIZON_ACQUISITION_BASIS_GAP`. Historical acquisition may predate
the supplied window. This state asserts neither parser/source defect nor a
purchase-sale relation. It blocks only the dependent exact `(asset, currency)`
group and unresolved disposal suffix; independent group calculations remain.

Each blocker binds the first unresolved disposal or invalid source fact, the
evidence searched, the precise insufficiency reason, and the kind of evidence
that could close it. FIFO results without a same-row direct expense remain
calculation evidence but are not promoted to Tax Model-ready inputs. The method
creates no new persistence and retains `invented_facts = 0`,
`invented_relations = 0`, and `reconciliation = not_performed`.

Partial acquisition commission and currency conversion are
`METHODOLOGY_UNRESOLVED`. This contract does not assert that relation evidence
is necessary for either future method.

The additive Issue #293 inspection helper is operation-local. It requires one
exact `disposal_fact_id`, selects that consumption security through the same
validated disposal-selection owner, and examines only the selected security's
`recognized_acquisition_cost.sources`. Commission details from any other
consumed security cannot satisfy the helper or create an acquisition-allocation
demand for the selected disposal.

## Required-input classification

Evidence matrices for this boundary may use only:

- `AVAILABLE`;
- `AVAILABLE_AFTER_SIMPLE_DETERMINISTIC_SELECTION`;
- `MISSING_FROM_SOURCE`;
- `LOST_UPSTREAM`;
- `METHODOLOGY_UNRESOLVED`.

Missing or incomplete required facts produce typed failures and no Tax Model or
declaration projection. Technical Gate 4 completeness is never promoted to
taxpayer-period completeness.

The preceding sentence is scoped to the affected calculation input. It does
not erase Tax Models already produced for independent complete groups.

## Non-goals

No projector cutover, public activation, persistence, legacy deletion, event
ontology, relation layer, reconciliation engine, broker adapter, currency
inference, or LLM decision is authorized.
