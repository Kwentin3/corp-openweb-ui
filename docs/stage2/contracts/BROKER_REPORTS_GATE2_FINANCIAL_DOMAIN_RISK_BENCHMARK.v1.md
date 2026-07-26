# Broker Reports Gate 2 Financial Domain Risk Benchmark

Status: target contract.

Version: `1.0.0`.

Date: 2026-07-26.

## 1. Purpose

This contract defines the GOAL 8 benchmark around product risk rather than
exact disposition distribution.

The benchmark consumes a frozen synthetic manifest and candidate decision or
query outcomes. It does not call a provider, replace the canonical validator,
materialize production data, or qualify a model. Candidate content is scored
by generic disposition, type identity, role/ref ownership, literal retention,
provenance, terminal ownership, and query completeness rules.

## 2. Versioned artifacts

```text
manifest=broker_reports_gate2_financial_domain_risk_benchmark_manifest_v1
policy=broker_reports_gate2_financial_domain_risk_policy_v1
result=broker_reports_gate2_financial_domain_risk_benchmark_result_v1
```

The manifest is canonical-JSON hash bound, frozen, synthetic, and declares
zero customer data. A committed aggregate-only safe result must be byte-for-
meaning reproducible by the deterministic scorer.

## 3. Absolute safety gates

The following blocker families are absolute:

```text
incorrect_typed_type
invented_value
invalid_ref
wrong_role
duplicate_or_cross_scope_binding
literal_or_provenance_loss
missing_terminal_owner
incomplete_query_response
```

Any nonzero blocker count makes the benchmark status `FAILED`. There is no
weighted score, tolerance, fallback, repair, or aggregate metric that can
override a hard blocker.

`incorrect_typed_type` includes an unsupported typed claim, a typed claim
against an unclassified/non-financial/unsupported reference, the wrong Pack
type, and an unsafe disposition change. The only explicitly safe disposition
relaxation is a typed reference becoming `unclassified_financial_input` while
all source values, provenance, scope, and terminal ownership remain intact.

## 4. Safe under-typing

Typed-to-unclassified is measured separately:

```text
typed_to_unclassified_total
safe_under_typing_total
safe_under_typing_rate
```

It is safe only when no hard blocker occurs. Missing or changed literals,
invalid refs, lost provenance, cross-scope bindings, or missing ownership make
the case unsafe even if its disposition is unclassified.

Safe under-typing lowers typed recall and raises the unclassified rate. It does
not lower typed precision and is not treated as unsafe typed
misclassification.

## 5. Quality metrics

Quality metrics remain visible but cannot hide a safety failure:

```text
typed_recall =
  correct_typed / typed_reference_total

classification_precision =
  correct_typed / candidate_typed_total

unclassified_rate =
  candidate_unclassified / semantic_decision_cases_total

layout_noise_handling_rate =
  safely_exact_layout_cases / layout_noise_cases_total

query_completeness_rate =
  exact_complete_queries / query_cases_total
```

Reference and candidate disposition distributions are retained as
observations with:

```text
primary_acceptance_gate=false
```

## 6. Generic binding and retention checks

Python benchmark code knows no Financial Semantic Pack type meaning. Type IDs,
roles, source refs, scope refs, literals, and provenance refs are fixture
data.

For each decision case the scorer checks:

- a typed claim uses exactly the referenced type identity;
- every bound ref belongs to the declared source values;
- each role maps to its referenced value;
- duplicate roles, duplicate values, duplicate bindings, and foreign scopes
  fail closed;
- retained literals equal the exact source literals;
- required provenance refs remain present;
- exactly one terminal owner exists and equals the referenced owner.

No financial words, headers, synonyms, type-specific regex, or type-specific
Python predicates are used by the scorer.

## 7. Deterministic structural pre-close

An obvious technical/layout outcome may close without model semantics only
from this closed structural evidence:

```text
source_supported: boolean
structural_role: closed layout role or opaque technical role
financial_value_candidates_total: non-negative integer
```

Rules:

- `source_supported=false` yields `unsupported`;
- a closed layout role with zero financial value candidates yields
  `no_financial_input`;
- every other combination returns no deterministic decision and must remain
  on the semantic route.

The pre-close does not inspect text, labels, financial meaning, Pack type IDs,
or regex matches. The manifest validator rejects a case declared
deterministic when the structural evidence does not prove its disposition.

## 8. Query completeness

A query case passes only when all of the following are exact:

- `query_result_complete=true`;
- `matching_records_total` equals the frozen matching set;
- `records_returned_through_page` equals that same total;
- ordered `{record_id, record_sha256}` pairs equal the complete frozen ordered
  set, binding the response to exact literal-bearing record content;
- every candidate result supplies its complete record object and the scorer
  recomputes `record_sha256` from canonical content before comparison;
- result IDs contain no duplicate;
- required provenance refs are present and no foreign ref is introduced.

Partial pagination presented as final, a missing or extra record, order drift,
changed record content/hash, duplicate records, false completeness, malformed
or foreign refs, or provenance loss is a hard failure. Candidate lists are
closed; malformed entries are rejected rather than filtered out.

## 9. Safe evidence

The safe result contains only:

- case IDs and route/kind labels;
- blocker codes and aggregate counts;
- aggregate quality metrics;
- disposition counts;
- manifest/result integrity hashes;
- zero-call/cost/fallback/repair accounting.

It contains no source literal, candidate payload, raw provider output,
customer data, secret, or private path.

## 10. Acceptance

```text
SAFETY_GATES=ABSOLUTE
SAFE_UNDERTYPING=MEASURED
EXACT_DISPOSITION_DISTRIBUTION=NOT_PRIMARY
QUERY_COMPLETENESS=TESTED
```

GOAL 8 acceptance establishes the benchmark policy and deterministic scorer.
It does not claim economy-model qualification, actual-corpus coverage,
production admission, or live-stage activation.
