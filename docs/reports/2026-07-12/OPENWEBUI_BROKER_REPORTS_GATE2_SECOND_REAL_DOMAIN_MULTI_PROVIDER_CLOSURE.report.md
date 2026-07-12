# OpenWebUI Broker Reports Gate 2: Second Real Domain And Multi-Provider Closure

Date: 2026-07-12
Scope: bounded Gate 2 candidate binding only

## Result

The remaining Gate 2 cross-domain and multi-provider architecture gap is
closed.

One real bounded `income` target from a complete normalized CSV source unit
produced the same five-candidate, one-relation package and one accepted typed
fact through:

- Gemini `models/gemini-3.1-flash-lite`;
- Anthropic `claude-haiku-4-5-20251001`;
- OpenAI `gpt-5.6-luna` as an optional control.

All three runs used strict provider structured output, the generic
candidate-binding materializer, the unchanged source-fact validator and the
deterministic stitcher. There was no fallback, repair, hidden failover or
free-form value extraction.

## Source and target diagnosis

The source-format class was a complete native CSV full-source unit. The
controlled local re-slice proved:

- one complete source document and one complete source unit;
- 1,342 selected source refs with complete coverage;
- 344 derived source units;
- 14 complete `position_snapshot` route targets;
- 98 high-confidence `income` route targets;
- no parent remainder and no truncated selected unit.

The prior position result was not caused by the provider, source-fact validator
or incomplete table projection. The selected position-routed row produced zero
mechanically admissible candidate values and zero relations. It therefore could
not satisfy the position profile requirement of instrument plus quantity or
valuation. Gemini returned an allowed fail-closed no-fact result; the binding
validator accepted the coverage decision. The row was not forced into a typed
position fact.

The selected `income` row was source-visible and mechanically sufficient. It
produced five candidates:

- one `decimal_amount` candidate;
- four `short_visible_label` candidates;
- one `same_row_candidate_group` relation.

No raw filename, row, value, account data, personal data, secret, local path or
environment value is included in this report.

## Refinement boundary

No source-fact schema, validator, provenance rule, domain profile, Prompt or
candidate kernel was weakened or changed.

The proof harness was aligned with the production input priority:

1. complete `full_source_unit` packages are no longer discarded by a harness
   that recognized only legacy `normalized_table_projection` input mode;
2. full-source tables run through the production segmenter before target
   selection;
3. the legacy bounded projection path remains supported;
4. provider audits now expose safe candidate/relation counts, binding outcome
   and provider execution aggregates without exposing private values.

An earlier attempt with `prefer_table_projections=true` selected the whole
1,342-row table projection and correctly hit the row-budget guard. The final
route uses the complete full-source unit and selects one bounded derived row.

## Provider results

Each provider attempt has its own extraction run, raw private output, schema
hashes, provider execution metadata, binding validation, source-fact validation
and stitch result in the private ArtifactStore.

| Provider/model | Transport | Result | Latency | Input/output tokens | Schema transforms |
| --- | --- | --- | ---: | ---: | ---: |
| Gemini `models/gemini-3.1-flash-lite` | OpenWebUI Gemini compatibility route | 1 typed `income`, passed | 4,365 ms | 13,525 / 514 | 49 |
| Anthropic `claude-haiku-4-5-20251001` | native Messages + `output_config.format` | 1 typed `income`, passed | 12,907 ms | 14,185 / 360 | 9 |
| OpenAI `gpt-5.6-luna` | OpenAI chat completions via OpenWebUI | 1 typed `income`, passed | 6,558 ms | 11,560 / 510 | 0 |

For every successful run:

- requested model id matched resolved model id;
- canonical and adapted request schema hashes were recorded;
- candidate set validation passed: 5 candidates;
- relation set validation passed: 1 relation;
- binding validation passed: selected/accounted refs 1/1;
- source-fact validation passed: 1/1 private fact;
- stitch completed: selected/accepted 1/1;
- conflict/uncovered/unknown/no-fact counts: 0/0/0/0;
- repair count: 0;
- fallback count: 0;
- Knowledge, vector, document and file deltas: 0.

## Local deterministic gates

The production factory path passed the candidate-binding test matrix:

- valid materialization for every supported domain, including `income` and
  `cash_movement`;
- package-bound candidate and relation ids;
- negative mutation matrix with typed fail-closed errors;
- ambiguity resolution requirements;
- missing-required-candidate rejection;
- issue carry-forward through the unchanged validator;
- complete deterministic stitch.

Focused candidate-binding suite: 10 passed.

Full Broker Reports proof suite: 217 passed in 24.697 seconds.
`git diff --check`: passed.

The irreversible boundary is persistence of a validated private source fact.
The tests and live runs assert the terminal fact/validation/stitch outcomes at
that boundary; they do not assert only model calls or snapshots.

## Existing cash regression

The focused all-domain production-factory regression passed the unchanged
`cash_movement` candidate-binding, source-fact validation and stitch path.
Existing deployed real native/PDF Gemini cash evidence remains valid. No runtime
contract or managed Prompt changed in this slice, so an additional customer
cash call was not needed.

## Provider architecture decision

Gemini compatibility transport is accepted as the production decision for this
bounded Gate 2 contract. It has now preserved structured output, provider schema
adaptation, canonical validation, typed real facts and zero fallback for real
`cash_movement` and `income`. A separate raw-native Gemini REST adapter is not a
remaining blocker while these invariants hold.

Anthropic uses the native Messages transport and `output_config.format`.
Credentials for all providers are resolved from OpenWebUI Admin Connections.
There is no Function-level duplicate credential store.

Routing is not based on table size. The selected models are approved budget
frontier extraction profiles. Cost-based routing, pricing models and automatic
provider failover remain outside scope.

## Repository, live parity and guards

The proof ran through:

`broker_reports_gate2_domain_source_fact_pipe -> Gate2DomainSourceFactRuntimeFactory.create`

The control, smoke and production route all retain the factory boundary. The
live verifier passed all Functions, 12 managed Prompts, provider profile/model
namespaces and factory anti-drift checks.

Repository/live bundle SHA parity:

- Gate 1: `3c1e9327ef3bfa118ee72c0a9d0ac7a2b3cedc6d65e75e9ae18d58ced31d379a`;
- Gate 2 source: `6d3c7d8a79ec151e592969f81971b674ef415ad55ecc9686bd0f043b846d0952`;
- Gate 2 domain: `4da61022696509b0588f8ef9cb5e01dfd0fa4b7688f04112f7a90bc75a5cc2c0`.

No OpenWebUI core patch or live Function/Prompt deployment was required because
the production runtime bundle was unchanged and already matched live. Changes
in this slice are proof-harness diagnostics, tests and canonical Stage 2 docs.

The real runs confirmed:

- ordinary processed upload was not used;
- Knowledge/RAG was not used;
- vectorization was not performed;
- OCR/VLM and page rendering were not used;
- no Gate 3, tax, declaration or XLS/XLSX work was performed.

## Final statuses

```text
GATE2_SECOND_REAL_DOMAIN_TARGET_READY
GATE2_SECOND_DOMAIN_CANDIDATE_BINDING_REFINED
GATE2_SECOND_DOMAIN_LOCAL_PROOF_PASSED
GEMINI_SECOND_REAL_DOMAIN_TYPED_FACT_PASSED
CLAUDE_SECOND_REAL_DOMAIN_TYPED_FACT_PASSED
GATE2_MULTI_PROVIDER_SECOND_DOMAIN_PROOF_PASSED
GATE2_SOURCE_FACT_VALIDATOR_PASSED
GATE2_ROW_COVERAGE_PROVEN
GATE2_SOURCE_VALUE_REFS_PROVEN
GATE2_ISSUE_CARRY_FORWARD_PROVEN
GATE2_PROVIDER_EXECUTION_METADATA_PROVEN
GATE2_GEMINI_COMPATIBILITY_TRANSPORT_ACCEPTED
GATE2_CASH_MOVEMENT_REGRESSION_PASSED
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
GATE2_NATIVE_PROVIDER_REAL_PROOF_PASSED
GATE2_CROSS_DOMAIN_REAL_ACCEPTANCE_PASSED
STAGE2_GATE2_ARCHITECTURE_CLOSURE_READY
```
