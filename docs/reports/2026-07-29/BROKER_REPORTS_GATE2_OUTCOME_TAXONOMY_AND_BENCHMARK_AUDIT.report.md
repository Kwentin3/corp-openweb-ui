# Broker Reports Gate 2 — Outcome Taxonomy and Benchmark Audit

Date: 2026-07-29

Status: `PASSED_LOCAL_ACCEPTANCE_PENDING_REVIEWED_GREEN_PR`

Base revision: `d6957865a97450136e2a5b9cabcf6e7e73aef0f3`

Branch:
`codex/broker-reports-gate2-outcome-taxonomy-goal6`

## 1. Outcome

GOAL 6 closes the missing semantic outcome between zero plausible managed
types and two-or-more plausible managed types.

The accepted
[Outcome Taxonomy v1](../../stage2/contracts/BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md)
is total over valid, sufficient model-visible context and selects one
additive managed reason:

```text
single_registry_type_no_safe_record
```

The reason applies only when exactly one managed financial type is plausible
but no complete prebound record can be selected safely. It is versioned in an
inactive catalog v2 candidate. It is not accepted by the active V6 Choice and
is not packaged into the historical managed-assets family.

An additive frozen outcome-audit manifest proves that three of the four
historical zero-choice expectations used the wrong semantic reason. The
historical manifests remain immutable. No model output was used to make these
corrections.

## 2. Authority and compatibility boundary

GOAL 6 read the existing architecture authority map, Semantic Pack, decision
reason catalog, Candidate Compiler, technical preclose, active V6 Choice,
historical V6 benchmark and successor-v2 fixture manifest.

Ownership remains singular:

- type and role meaning stays in the unchanged Financial Semantic Pack v1;
- complete Typed Options and binding blocks stay code-owned;
- active response codes and shape stay in the unchanged V6 Choice authority;
- the new reason wording lives only in the inactive catalog v2 successor;
- corrected expectations live only in the additive frozen outcome-audit
  manifest;
- future minimal projection stays with the existing managed-assets
  loader/projection owner;
- any future V2.1 response profile must remain in the existing Choice
  authority and requires separate explicit authorization.

The outcome-audit validator is offline validation support. It is not imported
by the runtime route, provider adapters, active benchmark runner or current
qualification workflow.

## 3. Total outcome taxonomy

`uniquely_safe_choice_count` means complete prebound choices remaining after
the whole source and every available type meaning are considered. Raw
Compiler choices, attempts and binding blocks do not establish semantic type
count.

| State | Plausible types | Safe choices | Route | Disposition / reason |
| --- | ---: | ---: | --- | --- |
| `typed_safe_1` | `1` | `1` | `semantic_model` | `typed_input / typed_supported` |
| `no_type_0` | `0` | `0` | `semantic_model` | `unclassified_financial_input / no_registry_type` |
| `ambiguous_type_2plus` | `2+` | `0` | `semantic_model` | `unclassified_financial_input / ambiguous_registry_type` |
| `single_type_no_safe_record` | `1` | `0` | `semantic_model` | `unclassified_financial_input / single_registry_type_no_safe_record` |
| `insufficient_source_context` | not assessed | not assessed | `technical_preclose` | applicable code-owned source/layout terminal outcome |
| `technical_failure` | not assessed | not assessed | `technical_preclose` | fail closed without a forced semantic disposition or reason |

The first four rows are mutually exclusive and total for valid, sufficient
semantic context. Insufficient context and technical failure remain outside
semantic reason selection and cannot be repaired into a semantic answer.

## 4. Count-one decision

The program allowed three possible resolutions:

1. add a managed reason;
2. use a separate non-semantic preclose;
3. prove the state impossible.

The evidence rejects options 2 and 3:

- the technical preclose is forbidden from interpreting labels, Pack
  meanings or managed type IDs;
- the frozen suite contains three sources for which exactly one type remains
  plausible while multiple candidate bindings prevent one safe record.

GOAL 6 therefore chooses option 1. Catalog v2 preserves both v1 entries and
adds exactly one code. Selection is closed over two dimensions:

| Reason | Plausible distinct types | Uniquely safe choices |
| --- | ---: | ---: |
| `no_registry_type` | `0` | `0` |
| `single_registry_type_no_safe_record` | `1` | `0` |
| `ambiguous_registry_type` | `2+` | `0` |

The new catalog is inactive, has no active response consumer, and carries the
explicit field/value `response_profile_status: not_implemented`.

## 5. Frozen zero-choice audit

Primary evidence comes from the immutable
`gate2_financial_successor_v2/manifest.json` source cells and the unchanged
Pack definitions. Compiler blocks are supporting mechanical evidence only.

| Frozen case | Plausible types | Why | Correct outcome |
| --- | --- | --- | --- |
| `syn_successor_v2_multiple_compatible` | cash; printed metric | The source separately states possible cash and possible total meanings. | `unclassified_financial_input / ambiguous_registry_type` |
| `syn_successor_v2_detail_vs_subtotal` | printed metric only | The source states fee detail and subtotal; no ordinary cash-state meaning is present, while two amount refs prevent one safe record. | `unclassified_financial_input / single_registry_type_no_safe_record` |
| `syn_successor_v2_adjacent_equal` | cash only | Cash-balance meaning is explicit, but two distinct equal-valued amount refs prevent one safe record. | `unclassified_financial_input / single_registry_type_no_safe_record` |
| `syn_successor_v2_adjacent_fx` | cash only | Cash-balance meaning is explicit, but two amount/currency candidates prevent one safe record. | `unclassified_financial_input / single_registry_type_no_safe_record` |

The resulting plausible-type counts are exactly:

```text
2, 1, 1, 1
```

The additive audit seals exact source and Pack JSON pointers for all four
cases. The historical ambiguous answer remains correct for the first case.
The latter three are benchmark errors because record-binding ambiguity inside
one type is not ambiguity between two or more distinct types.

## 6. Corrected expectation authority

The frozen
[`gate2_financial_semantic_v6_outcome_audit_v1` manifest](../../../services/broker-reports-gate1-proof/benchmarks/gate2_financial_semantic_v6_outcome_audit_v1/manifest.json)
contains all twelve case identities and all six taxonomy states.

It pins:

- historical V6 benchmark canonical SHA-256
  `3688fe9d47534cc6f810550561460f1508acd095e798ea90c5998b55c63b0d33`;
- successor-v2 base canonical SHA-256
  `430bea21d0a36e993bc50184d971f36dfc75a1d2be12bcf5e43fba7436797d66`;
- unchanged Pack semantic integrity
  `ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`;
- catalog v2 semantic integrity
  `2510b57b51749a14f76b987cddaa3eea19f1bb975a97c6c089565253dc3593e9`;
- its own canonical integrity
  `774acd03c95ddc2d898112b6b62e3bed54613cfeaac7f98689e7c05224d271ae`.

Only these three expected reasons change:

- `syn_successor_v2_detail_vs_subtotal`;
- `syn_successor_v2_adjacent_equal`;
- `syn_successor_v2_adjacent_fx`.

The active V6 runner still reads the historical V6 manifest. A later
corrected benchmark must use a new versioned runner derived from this audit;
it must not mutate or silently reinterpret the historical evidence.

## 7. Change scope

```text
CHANGED_FILES_TOTAL: FIFTEEN
NORMATIVE_CONTRACTS_ADDED: ONE
MANAGED_CATALOG_SUCCESSORS_ADDED: ONE
FROZEN_OUTCOME_AUDITS_ADDED: ONE
OFFLINE_VALIDATORS_ADDED: TWO
TEST_FILES_ADDED: TWO
CANONICAL_ROUTING_OR_CI_DOCS_UPDATED: SIX
DATED_REPORTS_OR_RECEIPTS_ADDED: TWO
ACTIVE_RUNTIME_ROUTE_CHANGES: ZERO
HISTORICAL_MANIFEST_CHANGES: ZERO
ACTIVE_CHOICE_CHANGES: ZERO
PROMPT_CHANGES: ZERO
PACK_CHANGES: ZERO
GENERATED_BUNDLE_CHANGES: ZERO
PROVIDER_CALLS: ZERO
FULL_BENCHMARK_RUNS: ZERO
```

Catalog v1, family v2, the decision source, active Choice, Prompt, Pack,
historical V6 benchmark manifest and successor-v2 base manifest remain
unchanged.

## 8. Local verification

The exact maintained GitHub Actions boundary passed locally:

- all three generated-asset checks passed;
- all three Function bundles rebuilt with zero byte diff;
- baseline-compatible Ruff correctness checks passed;
- the focused CI suite passed: 121 tests, 5 warnings, 32.41 seconds;
- the 28 new taxonomy/catalog/audit tests passed independently in 1.11
  seconds.

The tests cover:

- generated catalog-v2 schema validation;
- exact predecessor meaning preservation and exactly one added reason;
- all three `0 / 1 / 2+` semantic boundaries;
- exact twelve-case and six-state outcome-audit shape;
- exact three expectation corrections;
- exact four frozen evidence audits and counts `2, 1, 1, 1`;
- historical manifest, active Choice, Prompt and Pack byte identity;
- catalog/audit integrity and predecessor hash identity;
- fail-closed mutations of codes, boundaries, pointers, states, reasons and
  historical identities;
- absence of an active runtime or provider execution route.

Three targeted historical identity/tamper cases also passed without executing
the benchmark. Across all 15 changed files, 450 relative Markdown links
resolved with zero missing targets, all 3 JSON files parsed, the privacy scan
found zero unsafe markers, and `git diff --check` passed.

Two independent fresh reviews initially found fail-closed and canonical
vocabulary gaps. The final diff now pins the exact predecessor integrity,
new reason code, per-case plausible type tuples, ordered evidence pointers,
truth-table projection, route identities, active Choice/Prompt bytes and
closed import/consumer surface. Regression tests cover the corresponding
self-consistent reseal attacks. Re-review found no unresolved issue.

The full service suite was deliberately not run because it contains the
historical full benchmark proof boundary. GOAL 6 forbids representing that
benchmark as executed. No provider command, smoke, retry, repair or fallback
was invoked.

The repository-safe
[receipt](BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY_AND_BENCHMARK_AUDIT.receipt.safe.json)
records only synthetic case IDs, aggregate counts, hashes and verification
status. It contains no customer values, provider payloads, filesystem paths
or hidden traces.

The real GitHub Actions `broker-reports-ci` check and a fresh review of the
actual immutable GitHub diff remain required before merge. Local success is
not represented as a GitHub check.

## 9. Verdict and continuation

GOAL 6 passes local acceptance as an inactive taxonomy, managed-reason
successor and evidence-backed corrected-expectation audit. It does not
activate Context V2.1 or change production behavior.

GOAL 7 may begin only after this exact GOAL 6 head receives fresh review,
passes the real GitHub Actions check and is merged into `main`.

GOAL 7 may implement only the minimal managed projection. GOAL 8 may build
only the non-active V2.1 Packet candidate. There remains an explicit STOP
before GOAL 9 until a separately authorized versioned V2.1 response profile
exists in the current Choice authority or the governing program is amended.
