# Broker Reports Gate 2 Outcome Taxonomy v1

Status: `VERSIONED_INACTIVE_GOAL6_AUDIT_ACCEPTED_NOT_RUNTIME_ACTIVE`

Contract ID:
`broker_reports_gate2_outcome_taxonomy_v1`

## 1. Purpose

This contract closes the GOAL 6 semantic count-one gap without rewriting the
historical V6 benchmark, Prompt, Financial Semantic Pack, active V6 Choice or
technical-preclose policy.

It defines:

- the total decision truth table used by future Context V2.1 work;
- one additive managed reason candidate for the state in which exactly one
  type is plausible but no complete prebound record is safe;
- the evidence-backed correction of three frozen zero-choice expected
  answers; and
- the fail-closed boundary between semantic outcomes, insufficient source
  context and technical failure.

This contract is normative for GOAL 7 and later corrected benchmark work. The
dated GOAL 6 report and receipt are evidence only.

## 2. Authority split

| Concern | Sole owner |
| --- | --- |
| financial type and role meaning | unchanged Financial Semantic Pack v1 |
| complete code-owned Typed Options and binding blocks | unchanged Candidate Compiler and Typed Option factories |
| active V6 response codes and response shape | unchanged active V6 decision and Choice contracts |
| future count-one reason meaning | additive inactive Financial Decision Reason Catalog v2 candidate |
| audited expected answers | additive frozen V6 outcome-audit manifest v1 |
| current technical preclose | unchanged `Gate2FinancialSemanticV5PrecloseFactory.create` |
| future minimal model projection | existing managed-assets loader/projection owner, beginning in GOAL 7 |
| future V2.1 response profile | existing Choice authority, only after separate explicit authorization |

The catalog v2 candidate is a successor of the same catalog ID. It is not a
second active catalog, is not packaged into the historical family v2
manifest, and is not accepted by the active V6 Choice. Its validator owns
structure and integrity only; all human wording remains JSON-owned.

## 3. Evaluation order

The following order is normative:

1. Validate source support, scope, shape and integrity.
2. If the supported source contains no semantic financial context, return the
   applicable code-owned non-semantic terminal outcome without calling a
   model.
3. Build the sealed Evidence Bundle and complete code-owned Typed Options.
4. Compare the whole visible source with every available type meaning.
5. Select exactly one of the semantic rows in section 4.

A compiled-choice count, Compiler attempt count or blocked-binding count is
not a plausible-type count. In particular, `choices=[]` does not prove
`no_registry_type`, `ambiguous_registry_type`, or the new count-one reason.

## 4. Total truth table

`uniquely_safe_choice_count` means the number of complete prebound choices
that remain uniquely safe after the whole visible source and every available
type meaning are considered. It is not the raw Compiler output count.

| State | Plausible distinct available types | Uniquely safe choices | Route | Disposition | Reason |
| --- | ---: | ---: | --- | --- | --- |
| `typed_safe_1` | exactly `1` | exactly `1` | `semantic_model` | `typed_input` | `typed_supported` |
| `no_type_0` | exactly `0` | `0` | `semantic_model` | `unclassified_financial_input` | `no_registry_type` |
| `ambiguous_type_2plus` | `2` or more | `0` | `semantic_model` | `unclassified_financial_input` | `ambiguous_registry_type` |
| `single_type_no_safe_record` | exactly `1` | `0` | `semantic_model` | `unclassified_financial_input` | `single_registry_type_no_safe_record` |
| `insufficient_source_context` | not assessed | not assessed | `technical_preclose` | applicable code-owned terminal disposition | applicable code-owned source/layout reason |
| `technical_failure` | not assessed | not assessed | `technical_preclose` | no forced semantic disposition | no forced semantic reason |

The semantic rows are mutually exclusive and total over valid, sufficient
model-visible source context. The last two rows are outside semantic reason
selection and must never be repaired into one of the four semantic outcomes.

Both non-semantic rows use the exact route identity `technical_preclose`.
Their terminal policies differ: insufficient context returns an applicable
code-owned source/layout outcome, while technical failure fails closed
without forcing a semantic disposition or reason.

`insufficient_source_context` is not a synonym for count one. It covers a
supported input that cannot present semantic financial source context, such
as an authoritative layout-only case. `technical_failure` covers unsupported
source/extractor shape, integrity failure, invalid mapping or another
technical contract failure.

## 5. Count-one decision

GOAL 6 chooses the program's **new managed reason** option.

The exact candidate code is:

```text
single_registry_type_no_safe_record
```

Its title, meaning, usage, counter-usage, example and reciprocal contrasts
live only in the additive
[`broker_reports_gate2_financial_decision_reason_catalog.v2.json`](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v2.json).
The catalog uses two selection dimensions:

- `plausible_distinct_available_financial_type_count`;
- `uniquely_safe_prebound_choice_count`.

The count-one entry is pinned to `1` and `0`, respectively. The existing
reasons remain pinned to `0/0` and `2+/0`.

This decision does not authorize a response-schema change. The active V6
decision tuple, V6 Choice, Local Choice, normalizer, parser, Packet, Prompt,
provider adapters and runtime route remain unchanged. Until a separately
authorized V2.1 Choice profile accepts the new code, any request that requires
the count-one outcome is ineligible for provider transport.

## 6. Frozen zero-choice audit

Primary evidence is the frozen
[`gate2_financial_successor_v2` manifest](../../../services/broker-reports-gate1-proof/benchmarks/gate2_financial_successor_v2/manifest.json)
plus the unchanged Pack definitions. Compiler blocks are supporting
mechanical evidence only; they do not establish semantic type count.

| Case | Plausible managed types | Evidence-backed assessment | Correct disposition and reason |
| --- | --- | --- | --- |
| `syn_successor_v2_multiple_compatible` | `cash_balance_snapshot_v1`; `printed_financial_metric_v1` | The source separately states possible cash and possible total meanings. Both current type definitions remain plausible. | `unclassified_financial_input` / `ambiguous_registry_type`; unchanged |
| `syn_successor_v2_detail_vs_subtotal` | `printed_financial_metric_v1` only | The source states fee detail and a subtotal. The subtotal can be a source-printed metric; no ordinary cash-class state meaning is present. The two amount refs do not identify one safe record. | `unclassified_financial_input` / `single_registry_type_no_safe_record`; corrected |
| `syn_successor_v2_adjacent_equal` | `cash_balance_snapshot_v1` only | The source states cash-balance semantics with two distinct amount refs containing the same literal. Printed-metric meaning is not stated, and one amount ref cannot be selected safely. | `unclassified_financial_input` / `single_registry_type_no_safe_record`; corrected |
| `syn_successor_v2_adjacent_fx` | `cash_balance_snapshot_v1` only | The source states cash-balance semantics with two amount/currency candidates. Printed-metric meaning is not stated, and the current single-record boundary cannot bind one pair safely. | `unclassified_financial_input` / `single_registry_type_no_safe_record`; corrected |

The exact primary evidence pointers and Pack pointers are sealed in the
additive
[`gate2_financial_semantic_v6_outcome_audit_v1` manifest](../../../services/broker-reports-gate1-proof/benchmarks/gate2_financial_semantic_v6_outcome_audit_v1/manifest.json).

The resulting plausible-type counts are exactly:

```text
2, 1, 1, 1
```

Three historical expected answers are therefore proven benchmark errors.
They are corrected from `ambiguous_registry_type` to
`single_registry_type_no_safe_record` independently of every model answer.

## 7. Historical and corrected benchmark identities

The following artifacts remain immutable historical inputs:

- `gate2_financial_successor_v2/manifest.json`;
- `gate2_financial_semantic_v6/manifest.json`;
- the active V6 benchmark validator and local proof;
- all prior reports, receipts and provider evidence.

The additive outcome-audit manifest is the expected-answer authority for
future corrected benchmark work. It:

- references the exact historical/base canonical hashes;
- preserves all twelve case identities and mechanical expected-option counts;
- changes only the three proven semantic reason errors;
- records the six taxonomy states and all four zero-choice audits;
- is not consumed by the active V6 qualification route; and
- records `provider_calls=0` and `full_benchmark_run=false`.

GOAL 13 must use a versioned corrected runner derived from this audit identity.
It must not mutate or silently reinterpret the historical V6 manifest.

## 8. Minimal-surface mapping

For every catalog v2 reason retained by GOAL 7, the Minimal Model Surface rule
remains:

| Minimal field | Exact managed source |
| --- | --- |
| `code` | exact catalog `code` |
| `title` | exact catalog `human_title` |
| `use_when` | exact first sentence of catalog `meaning` |

The first-sentence rule remains the exact prefix through the first U+002E
FULL STOP followed by one ASCII space or end of string. GOAL 7 projects the
catalog v2 candidate through the existing loader/projection owner without
copying reason wording into Python, Prompt, Packet or an adapter.

The historical Minimal Model Surface v1 contract and GOAL 5 receipt remain
unchanged. This contract is its additive GOAL 6 taxonomy successor.

## 9. Compatibility stops

The following are explicit stops:

1. Catalog v2 is inactive and has no active response consumer.
2. GOAL 7 implements only the managed minimal projection; it does not
   activate or invent a response schema.
3. GOAL 8 implements only the non-active
   [V2.1 Packet candidate plus private mapping receipt](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md).
4. Before GOAL 9, a separately authorized/versioned V2.1 response profile
   must exist in the existing Choice authority, or the program must be
   amended. GOAL 9 remains linter-only.
5. No provider smoke may include a count-one case until that response profile
   accepts and defines the new reason.
6. Prompt and Pack changes are not authorized by this audit.
7. The full benchmark is not authorized or executed by GOAL 6.

## 10. Verification contract

GOAL 6 is accepted only when:

- the additive catalog v2 and schema validate and have exact semantic
  integrity;
- catalog v1, family v2, active decision/Choice, Prompt and Pack bytes remain
  unchanged;
- the additive benchmark audit validates against exact historical hashes;
- all four zero-choice cases have evidence-backed type sets and outcomes;
- mutations of taxonomy, evidence pointers, expected reasons or predecessor
  identities fail closed;
- provider calls are zero; and
- the full benchmark was not run.

```text
OUTCOME_TAXONOMY: TOTAL_OVER_VALID_CONTEXT
COUNT_ONE_DECISION: NEW_INACTIVE_MANAGED_REASON
CORRECTED_EXPECTED_ANSWERS: THREE
HISTORICAL_MANIFESTS_MODIFIED: ZERO
ACTIVE_CHOICE_CHANGED: NO
PROMPT_CHANGED: NO
PACK_CHANGED: NO
PROVIDER_CALLS: ZERO
FULL_BENCHMARK: NOT_RUN
```
