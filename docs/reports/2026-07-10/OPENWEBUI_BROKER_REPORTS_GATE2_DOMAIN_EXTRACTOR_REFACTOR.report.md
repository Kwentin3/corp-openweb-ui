# OpenWebUI Broker Reports Gate 2 Domain Extractor Refactor Report

Date: 2026-07-10

Scope: research, contracts, implementation, local proof, live synthetic proof,
and one smallest controlled `case_group_002` primary vertical.

This report contains safe aggregate evidence only. It contains no customer
filename, OpenWebUI file id, path, raw row, source text, account, personal data,
secret, or environment value.

## Result

Gate 2 now has a production domain-specific structured extraction path:

```text
validated domain_context_packet_v0
  -> deterministic source-unit router
  -> narrow domain packages
  -> managed OpenWebUI Prompt per domain
  -> provider-native strict JSON Schema
  -> deterministic package-bound candidate finalizer
  -> unchanged strict source-fact validator in domain mode
  -> private validator-passed broker_reports_source_facts_v0
  -> deterministic stitcher / ownership / coverage validator
  -> safe compact Russian summary
```

The broad extractor remains available for compatibility and synthetic
comparison. It is not the intended customer default when the domain Function
and managed Prompts are available.

The live synthetic domain proof passed across all nine domains. A minimal real
`case_group_002` vertical also passed, but it is explicitly an
`unknown_source_row` fallback vertical over one truncated source unit. It proves
the real provenance/value/issue/validation/stitch boundary, not useful typed
domain extraction and not primary expansion readiness.

No primary expansion, non-primary extraction, Gate 3, tax, declaration, or
XLS/XLSX work was performed.

## Why the broad extractor failed

The first controlled broad real batch had 3/3 rejected packages and 0 accepted
fact sets. Across initial and repair attempts, the strict validator reported:

| Code | Count |
| --- | ---: |
| `source_fact_provenance_missing` | 66 |
| `source_fact_completeness_overstated` | 14 |
| `source_fact_coverage_gap` | 5 |
| `source_fact_issue_not_carried` | 4 |
| `source_fact_missing_field` | 1 |

One model call had to choose among nine fact branches, construct row/cell/value
provenance, copy issue policy, choose conservative completeness, populate
type-specific fields, and reconcile all selected refs. The package contained
valid refs, but exposed the whole bounded unit ref space. This was a task and
projection overload. The validator behaved correctly and was not relaxed.

## Implemented architecture

### Deterministic router

`Gate2SourceUnitRouterFactory` emits
`broker_reports_source_unit_domain_route_v0`. Every selected ref receives
exactly one ordered route entry.

Signals are limited to exact fact hints, normalized safe headers, exact/helper
visible labels, non-content value kinds, passport/usage safe projections,
provenance, coverage kind, and issue refs. Unicode helper tokens are supported.
Patterns are routing hints only; they do not parse or mint facts.

The router produces at most two candidates, a primary suggestion, confidence,
reason codes, allowed extractor ids, issue refs, and an unknown fallback.
Header/blank/layout refs become deterministic no-fact coverage and are not sent
to a model.

### Narrow domain packages

`Gate2DomainPackageBuilderFactory` emits
`broker_reports_domain_extraction_package_v0`. It physically narrows together:

- model rows/segments;
- private normalized cells/text;
- row/cell/segment provenance;
- source-value index;
- evidence/source-value/issue whitelists;
- coverage expectation;
- allowed fact types.

Internal payload indices are re-indexed only inside the narrow private package;
original opaque refs remain stable and the existing mechanical value
reproduction validator still succeeds.

### Managed domain Prompts and structured output

Nine managed OpenWebUI Prompts are installed, one per extractor domain. Final
prompt bodies are rendered from the repository contract and live only in
OpenWebUI Prompt management. Python, the Pipe, bundled Function, and Valves
contain prompt identities and policies, not final bodies.

Each provider schema retains the canonical source-facts union envelope but
removes fact variants outside the domain's allowed set. The package-bound
projection additionally limits fact count to candidate count and constrains
evidence/value/extracted/source-location ref arrays to whitelist enums.

Provider-native `response_format=json_schema`, `strict=true` is required.
Customer fallback is none. The post-validator separately repeats domain type,
scope, provenance, value, issue, privacy, boundary, and coverage checks.

Canonical source-facts schema SHA-256:

```text
2fcf8ef920e7aceae6fef898d4a4c375db7ab0cd73416bd9e19f76d57bff6da4
```

Final installed domain Function bundle SHA-256:

```text
1ad0ea8e30bbe03b4339a9796ec19b74d52d9bb69ad275421a649393d8a07a3d
```

Live content hash matched the bundle hash and the Function was active.

### Deterministic candidate finalizer

`Gate2DomainCandidateFinalizerFactory` runs after private raw-output persistence
and before semantic validation. It cannot create a fact or choose/change its
type. It may bind only values already proven by the package:

- run/package/document/unit scope and pending states;
- prompt/schema/model audit constants;
- selected row/segment location and row-bound evidence refs;
- issue refs/impact, conservative completeness, and downstream false flags;
- exact-header mechanical date/amount/currency/quantity/instrument candidates
  whose source-value refs reproduce successfully.

It does not invent a ref/value, add a no-fact reason, resolve an issue, or hide
incomplete coverage. The unchanged validator decides acceptance.

### Validator and system of record

The existing source-fact validator remains final authority. Domain mode adds
only:

- domain package artifact identity support;
- explicit `allowed_fact_types` rejection;
- the same ArtifactStore/lifecycle/resolver requirements.

Validator-passed `broker_reports_source_facts_v0` remains the private
system-of-record. `broker_reports_domain_source_facts_v0` is a safe wrapper
containing refs, ids, types, coverage refs, and validation status, not copied
private fact values.

### Stitcher and ownership

`Gate2SourceFactStitcherFactory` accepts only validator-passed domain outputs.
For every route-selected ref:

- deterministic no-fact coverage wins for header/blank/layout refs;
- one typed claim owns the ref;
- multiple typed claims create an explicit conflict and no owner;
- typed plus unknown selects typed;
- unknown-only claims collapse to one coverage-preserving unknown owner;
- an allowed no-fact claim accounts for the ref;
- otherwise the ref is uncovered.

V0 enables no multi-fact rule. Duplicate ids create conflicts. Complete status
requires no conflicts and no uncovered refs. Stitch results always forbid
cross-document consolidation, tax calculation, declaration mapping, and
XLS/XLSX generation.

## ArtifactStore placement

| Artifact | Visibility | Backend |
| --- | --- | --- |
| domain route | `safe_internal` | `project_artifact_store` |
| domain package | `private_case` | `project_artifact_payload` |
| raw model output | `private_case` | `project_artifact_payload` |
| canonical source facts | `private_case` | `project_artifact_payload` |
| source-fact validation | `safe_internal` | `project_artifact_store` |
| domain source-facts wrapper | `safe_internal` | `project_artifact_store` |
| stitch result | `safe_internal` | `project_artifact_store` |
| compact summary | `chat_visible` | `project_artifact_store` |

No artifact in this flow uses `openwebui_knowledge`, ordinary processed upload,
RAG, or vectorization.

## Local verification

Baseline before the refactor: 106/106 tests passed.

Final verification:

```text
python -m unittest discover -v -s tests
Ran 115 tests
OK

python -m compileall broker_reports_gate1 openwebui_actions scripts
passed
```

New tests cover:

- clean trade, income, withholding, fee, cash, ambiguous, unknown, header,
  blank, and layout routing;
- Unicode/exact helper routing;
- no selected-ref drop;
- physically narrow row/value projections;
- provider fact-type/ref/max-count constraints;
- deterministic finalizer boundaries;
- managed domain Prompt contract resolution;
- domain runtime ArtifactStore persistence and strict validation;
- double typed claims as conflicts;
- unknown/no-fact coverage and rejected candidates;
- closed-world bundled Function execution.

## Live synthetic proof

Model: `gpt-5.4-mini-2026-03-17`.

The final synthetic run used three private process=false artifact documents and
all nine managed domain Prompts.

| Metric | Result |
| --- | ---: |
| route artifacts | 3 |
| domain packages | 9 total / 9 accepted / 0 rejected |
| managed domains used | 9/9 |
| strict raw outputs | 10/10 |
| repair outputs | 1 |
| fallback outputs | 0 |
| canonical source-facts sets | 9, all private and validated |
| facts | 9, one per fact type |
| stitch results | 3/3 complete |
| selected refs | 12 |
| typed fact-owned refs | 8 |
| unknown refs | 1 |
| deterministic no-fact refs | 3 |
| conflicts / uncovered refs | 0 / 0 |
| issue/fact links | 4 |

Synthetic ambiguous/double-claim conflict behavior is proven by the local
deterministic fixture. The live clean run proves real OpenWebUI Prompt,
provider-schema, validator, ArtifactStore, and lifecycle wiring.

Infrastructure delta during the final live synthetic run:

```text
document rows: 0
file rows: 0
Knowledge rows: 0
vector collections/directories/files/bytes: 0
ArtifactStore Knowledge-backend records: 0
```

The final synthetic case created 73 scoped ArtifactStore records and was purged
through the ArtifactStore lifecycle after the proof.

Two earlier fail-closed iterations were retained only long enough for safe
error-code diagnosis and then purged. Acceptance improved from 1/9 to 7/9 and
finally 9/9 by narrowing deterministic responsibilities and provider ref/count
constraints; no validator rule was removed or weakened.

## Real `case_group_002` vertical

Safe preflight audited 16 primary source units. It found no complete
one/two-typed-domain target with high routing confidence:

- typed table units required 3–4 domains including unknown coverage;
- one-domain summary units contained 20–182 candidate segments;
- every real unit was marked truncated.

The smallest complete target was therefore chosen explicitly as an unknown
coverage fallback:

```text
primary documents in wave: 12
selected documents: 1
deferred primary documents: 11
selected source units: 1
selected refs: 5
extractor domains: unknown_source_row only
model candidates: 4
deterministic no-fact refs: 1
route issue refs: 4
source slice truncated: true
non-primary documents run: 0
```

Terminal result:

| Metric | Result |
| --- | ---: |
| domain packages | 1 total / 1 accepted / 0 rejected |
| strict raw outputs | 1, private |
| fallback outputs | 0 |
| validations | 1 passed / 0 errors |
| canonical source-facts sets | 1 private and validated |
| facts | 4 `unknown_source_row` |
| stitch results | 1 complete |
| coverage | 5 selected = 4 unknown + 1 no-fact |
| conflicts / uncovered | 0 / 0 |
| issue/fact links | 16 from 4 route issues |
| Gate 3 handoff ready | false |
| primary expansion allowed | false |

There were zero provenance-missing, completeness-overstated, coverage-gap,
issue-not-carried, or other validation findings. No rejected real raw output
existed; the single raw output remained private.

Infrastructure delta:

```text
ArtifactStore records: +9 expected scoped artifacts
document rows: 0
file rows: 0
Knowledge rows: 0
vector collections/directories/files/bytes: 0
ArtifactStore Knowledge-backend records: 0
```

This proves the real domain runtime, strict output, provenance/value refs,
issue carry-forward, complete selected-unit coverage, private persistence, and
stitch boundary. Because all four facts are fallback unknowns and the source
unit is truncated, it does not prove useful typed extraction or whole-source
coverage.

## Expansion decision

Not ready to expand `case_group_002` primary domain extraction.

Specific blockers:

1. the passed real vertical is unknown-only, not a typed domain fact proof;
2. every available real source unit is truncated;
3. the safe preflight found no complete high-confidence one/two-typed-domain
   unit;
4. non-primary must remain withheld until a typed primary vertical passes;
5. Gate 3 and intermediate-ledger readiness are not proven.

The next safe slice is to improve deterministic source-unit segmentation and
safe routing signals so one complete typed unit fits one or two domains, then
repeat the same one-unit proof. It is not safe to widen the current model task
or weaken validation.

## Proven statuses

```text
GATE2_DOMAIN_EXTRACTOR_RESEARCH_READY
GATE2_SOURCE_UNIT_ROUTER_READY
GATE2_DOMAIN_EXTRACTION_CONTRACTS_READY
GATE2_DOMAIN_PACKAGE_BUILDER_READY
GATE2_DOMAIN_STRUCTURED_OUTPUT_READY
GATE2_SOURCE_FACT_STITCHER_READY
GATE2_DOMAIN_EXTRACTOR_SYNTHETIC_PASSED
GATE2_REAL_VERTICAL_SOURCE_FACT_PASSED
GATE2_ROW_SEGMENT_COVERAGE_PROVEN
GATE2_ISSUE_CARRY_FORWARD_PROVEN
CASE_GROUP_002_DOMAIN_VERTICAL_EXTRACTION_PASSED
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
```

Not emitted:

```text
READY_FOR_CASE_GROUP_002_GATE2_PRIMARY_DOMAIN_EXTRACTION_EXPANSION
```
