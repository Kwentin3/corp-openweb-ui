# Broker Reports Gate 2 Financial Decision Reason Catalog v1

Status: `VERSIONED_INACTIVE_DRAFT_PROJECTED_ONLY_IN_NON_ACTIVE_CONTEXT_V2_0`

Catalog ID:
`broker_reports_gate2_financial_decision_reason_catalog`

Semantic version: `1.0.0`

Managed family:
`broker_reports_gate2_financial_domain_assets@1.1.0`

## 1. Purpose

This contract defines the single managed source of human-readable meaning for
the Gate 2 `unclassified_financial_input` reason codes.

The exact wording lives only in the
[catalog JSON](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v1.json).
This document defines ownership and validation boundaries; it does not repeat
the catalog prose and therefore cannot drift into a second meaning authority.

## 2. Authority split

| Concern | Sole owner |
| --- | --- |
| closed reason-code set and response shape | `broker_reports_gate2_financial_evidence_decision_v1` and V6 Choice |
| human-readable title, meaning, usage, counter-usage, example and contrast | this versioned catalog JSON |
| catalog structure, code-set parity, integrity and distinction checks | `Gate2FinancialDecisionReasonCatalogContractFactory` |
| financial type and role meaning | Financial Semantic Pack |
| model-visible projection | exact completeness projection implemented only in the non-active [Context V2.0 baseline](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md), through the existing single managed-assets loader and existing Pack projection owner; future minimal projection not implemented |

The catalog does not own dispositions, type IDs, type definitions, roles,
Typed Options, aliases, bindings, provider behavior, validation,
materialization or expected benchmark answers.

## 3. GUI-ready data contract

The catalog is strict JSON with:

- a stable catalog ID and semantic version;
- locale and disposition scope;
- inactive draft lifecycle metadata;
- a GUI collection title, stable item key, label field, display order and
  explicit editable/immutable field lists;
- one entry for every code obtained from the existing decision contract;
- `human_title`, `meaning`, `use_when`, `do_not_use_when`,
  `positive_example` and reciprocal
  `contrast_with_neighbouring_reasons`;
- a data-owned selection boundary;
- canonical semantic integrity.

The generated
[JSON Schema](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v1.schema.json)
is byte-derived from the Python contract factory. GUI tooling may consume the
JSON and schema, but direct GUI edits are not publication and cannot mutate
active runtime.

### Minimal model projection mapping

The
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
does not change this full catalog or author new human wording. It selects a
future reason card containing only exact catalog `code`, exact `human_title`
as `title`, and the exact first sentence of catalog `meaning` as `use_when`.
“First sentence” is the exact prefix through the first U+002E FULL STOP
followed by one ASCII space or end of string, with no trim, normalization,
summary or synonym substitution. The full catalog `use_when` remains backend
administration and is not the source of the minimal field.

Those exact source strings already exist. GOAL 6 completed the
outcome-taxonomy/count-one audit, GOAL 7 implemented this deterministic mapping
through the existing managed-assets loader/projection owner without embedding
replacement wording, and GOAL 8 built only the PacketFactory V2.1 candidate
plus private receipt. The later explicit program authorizes GOAL 9 to add the
inactive
[Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md)
profile in the existing Choice authority. Catalog JSON and projection bytes
remain unchanged; active Choice/runtime also remain unchanged. GOAL 10 owns
the later linter/sealed request after reviewed, green, merged GOAL 9.

## 4. Mechanical distinction

All reasons share the catalog selection metric
`plausible_distinct_available_financial_type_count`.

The data-owned boundaries are non-overlapping and collectively pin:

- one reason to the closed interval `0..0`;
- one reason to `2..unbounded`.

Every entry must contrast itself with every other reason exactly once and may
not contrast with itself. The factory checks those invariants generically,
without embedding the catalog's human wording or a Python mapping from a
specific code to a specific boundary.

Count `1` is intentionally outside these two reason boundaries. A uniquely
identified type with unresolved value or binding uncertainty must not be
silently relabelled as one of these two reasons.

## 5. Python-owned schema and checking

`Gate2FinancialDecisionReasonCatalogContractFactory` receives the maintained
decision-contract source as input and extracts `UNCLASSIFIED_REASON_CODES`
through Python AST. It does not define a second reason-code tuple.

The factory:

1. generates the closed Draft 2020-12 JSON Schema;
2. checks exact catalog identity and inactive lifecycle;
3. checks exact code-set parity;
4. checks complete human fields and unique display order;
5. checks reciprocal contrasts and non-overlapping selection boundaries;
6. verifies canonical SHA-256 after removing only top-level
   `integrity_sha256`.

It receives content from the existing managed-family builder. It performs no
filesystem, environment, network, provider or runtime access. Its source
contains no catalog human wording and no financial type definitions.

## 6. Identity and integrity

```text
CATALOG_GIT_BLOB_SHA256:
e5ca49c436113d5eebec189dae26d5a289287c214292eb32c80b547c29e56a0a

CATALOG_SEMANTIC_INTEGRITY_SHA256:
d7290593410cafd6b35281ed3a6159802f0d7e87b7a085f3ec2cd2b46f4a3e15

CATALOG_CANONICAL_SEMANTIC_BYTES:
3603

GENERATED_SCHEMA_GIT_BLOB_SHA256:
a2285297bc1332778293b24a195dcf0dc5631e3e62076185f7336442e250a68c
```

The Git-blob boundary is LF-normalized UTF-8 repository text. Semantic
integrity is canonical UTF-8 JSON with lexicographically sorted object keys,
preserved array order, no whitespace and only `integrity_sha256` omitted.

## 7. Lifecycle and rollback

This version is `draft`, `target_normative_not_live` and
`runtime_activation=false`.

- Draft rollback: discard this catalog/family candidate without runtime
  mutation.
- Future active rollback policy: select the previous validated immutable
  family version.
- Exact repository rollback target: family `1.0.0`, pinned by the family v2
  manifest.

The complete live family publisher, exact full-family readback and operational
rollback remain explicit gaps. This draft does not claim that those controls
already exist.

## 8. Compatibility stop

This catalog is model-visible only inside the exact non-active Context V2.0
completeness sidecar and does not claim frozen V6 benchmark conformance. The
[Context V2.0 contract](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
requires one readable card for every active Pack/Registry type compatible
with the Evidence Bundle source family, including types for which no Typed
Option exists. Candidate Compiler attempted types are a private parity check,
not the source of the visible type set and not evidence of semantic
plausibility. GOAL 4 implements and locally validates that closed projection;
it does not implement a response schema, request route or provider transport.
That historical full reason-card projection is not evidence that the
Minimal Model Surface projection has been implemented. Its exact first-sentence
selection rule is accepted by GOAL 5, while implementation remains GOAL 7.

Count `1` remains outside both catalog boundaries, and some historical cases
may still describe association ambiguity rather than two distinct plausible
type meanings. The Pack wording, Prompt, active packet payload/Choice, expected
answers and request/provider route remain unchanged; the packet runtime changes
only by adding the non-active sidecar.

## 9. Acceptance

The following is the frozen catalog-v1 acceptance snapshot. Its GOAL labels
record the prior program state and are not current continuation routing:

```text
CATALOG: VERSIONED_GUI_READY_DRAFT
CODE_SET_AUTHORITY: EXISTING_DECISION_CONTRACT
HUMAN_MEANING_AUTHORITY: CATALOG_JSON_ONLY
PYTHON_HUMAN_WORDING: ZERO
RUNTIME_ACTIVATION: FALSE
ROLLBACK_POLICY: DEFINED_NOT_LIVE_PROVEN
TYPE_MEANINGS_CHANGED: NO
PROVIDER_CALLS: ZERO
BENCHMARK_CONFORMANCE: NOT_CLAIMED
CONTEXT_V2_0_COMPLETENESS_PROJECTION: IMPLEMENTED_NON_ACTIVE
MINIMAL_REASON_PROJECTION: NOT_IMPLEMENTED_GOAL_7
CONTEXT_V2_1: NOT_IMPLEMENTED_GOAL_8
CONTEXT_V2_1_RESPONSE_PROFILE: NOT_IMPLEMENTED_SEPARATE_AUTHORIZATION_REQUIRED
CONTEXT_V2_1_LINTER: BLOCKED_BY_RESPONSE_PROFILE_STOP_GOAL_9
ACTIVE_MODEL_ROUTE: UNCHANGED
```

Current routing records GOAL 7 projection and GOAL 8 Context V2.1
candidate/private receipt as complete. The current GOAL 9 slice adds only the
inactive Choice-owned response profile; GOAL 10 owns the later linter and
sealed request after reviewed, green, merged GOAL 9.
