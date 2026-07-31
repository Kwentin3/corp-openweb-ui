# Broker Reports KT2 Same-Source Type-First Proof

Date: 2026-07-31

Status: `PASSED`; implementation merged, post-merge verification passed,
closure evidence becomes terminal only after its evidence PR is merged.

## 1. Authority

- Base authority: `38695a9275558f89f1a999f61fd19bd228efdf75`.
- Clean authority worktree: `../corp-openweb-ui-kt2`.
- Implementation branch:
  `feat/broker-reports-kt2-same-source-type-first-proof`.
- Implementation PR: #241, reviewed by agent boundary audit, GitHub CI green,
  merged.
- Implementation head: `58162383b27223c057f9e62ce600c8d7253c47b7`.
- Implementation merge:
  `16fe3d2b2dd68bbb6440ede3a9b7537849de7456`.
- Corrective PR #242 changed only the canonical-context lifecycle test so the
  evidence-only transition from `NOT_STARTED` to the exact terminal state can
  remain CI-enforced. It merged as
  `24948360095a749e11b1b0bcedbb8ae871a6b7f8` after review and green CI.
- Initial and pre-evidence open Broker Reports PR inventory: empty.

The accepted route is Option A: one inactive subordinate capability inside the
existing source-fact product boundary. PR #232 was not used as a base and none
of its implementation was imported.

## 2. Real same-source corpus

One existing real Gate 2 package was rebuilt through the current
`Gate2TablePackageFactory` path. Three bounded real source-unit payloads were
selected from that same source family. Private values and refs remain only in
ignored local evidence.

Privacy-safe identities:

- real package SHA-256:
  `f4e0df64290d2d8472175e6044b0da87650548d7e33a5463b1f12e8d2333a33f`;
- real unit payload hashes:
  `a3ba5bbd43fbcfe86d502e37aea92980ba5a7c095e97fbabb281381000e07db0`,
  `dcfa3ec4efd7990432f43fede893be0003306c8a6dcb2e9ee6d33f63a9d7ac1b`,
  `51ef57a5766eca32bf16d6d6f8d0982dc0884167ec332070281e6293a48d9e7c`;
- parent source-unit identity:
  `968732a7cd34e882a2bac774adde8f73305641ee488ee44caffdd9c4cbfb5d88`;
- public structural fixture SHA-256:
  `883c5352b2d4c5a24064467d4349a9b0e7eb4d981dc6967ae62bfddaf0fad212`;
- public corpus integrity:
  `9a2c015b24be2e29cb72ea31839757fdaef52a45e31c56d002971ee5b0eb576c`.

The public fixture preserves row graph, unit boundaries, field roles, source
ref topology, and ambiguity shape while replacing literal values. It includes
one full-package structural copy, three real-unit structural copies, and four
explicitly labelled `DETERMINISTIC_ADVERSARIAL_DERIVATION` cases. No derived
case is represented as a real document.

## 3. Type Cards and sealed options

The model-facing projection is
`broker_reports_gate2_financial_type_card_projection_v1`. It is generated from
the existing Semantic Pack/model-asset authority and contains two opaque cards
with display name, definition, positive/negative signals, competitors,
counterexamples, supported source shapes, and projection version.

Projection hash:
`704f4d09463308aa65c6e895936d0af92e387f15b624d5ea7610496cb2c4e8d6`.

The request contains bounded source units and opaque `tNN` keys. It contains no
canonical type IDs, source refs, prebound options, expected answers, reasons,
provider metadata, or activation signal. No regex/synonym shortlist is used.

Four exact options are produced by the existing candidate compiler and kept in
the sealed mapping. Each option binds one local option key, local type key,
existing canonical type, source unit, code-owned role bindings, exact refs,
constructibility, and integrity hash. The model generates no value, ref, role,
field name, fact, or materialized output.

- Request schema: `broker_reports_type_first_request_v1`.
- Response schema: `broker_reports_type_first_response_v1`.
- Sealed request hash:
  `7d18d7236b67a70f0b2781df9f90fe0fec1bb5ddf64c8166cca138b82109538b`.
- Sealed mapping hash:
  `37d115a2474d954894501dfe1025659507c153be5558e202cb6791953d2f9bdc`.

The response is a frozen simulated object with exact request, mapping, Pack,
and ordered unit coverage hashes. Empty and plural plausible-key arrays are
valid. Unknown/duplicate keys, extra fields, canonical IDs, values, refs,
reasons, missing/reordered units, and hash mismatches fail closed. There is no
retry, repair, fallback, or provider transport.

## 4. Same-source orchestration and owners

```text
existing Gate 2 package and segmentation
-> Gate2FinancialSemanticContractFactory
-> Pack-backed opaque Type Cards
-> Gate2FinancialCandidateCompilerFactory
-> Gate2FinancialSemanticV6ChoiceContractFactory
-> Gate2FinancialSemanticV6DecisionExpansionFactory
-> Gate2FinancialEvidenceValidatedDecisionFactory
-> Gate2FinancialEvidenceMaterializerFactory
-> Gate2FinancialSemanticV6DecisionEvidenceFactory
-> ArtifactStoreFactory / ArtifactResolver
```

`Gate2SameSourceTypeFirstProof` is an inactive subordinate of
`current_source_fact_orchestration`. The sole product owner remains
`Gate2DomainSourceFactRuntimeFactory`. It has no product entrypoint, provider
client, second parser, validator, materializer, replay owner, or canonical
shape. `AnswerContextSelectionFactory` remains a post-completed-Gate-2
consumer and is not called by the proof.

## 5. Materialized and fail-closed traces

The primary three-unit execution is:

| Unit | Plausible types | Exact restored options | Code reason | Result |
| --- | ---: | ---: | --- | --- |
| `u01` | 2 | 2 | `MULTIPLE_PLAUSIBLE_TYPES` | unclassified |
| `u02` | 1 | 1 | `UNIQUE_PLAUSIBLE_TYPE_AND_EXACT_OPTION` | typed through existing validator/materializer |
| `u03` | 0 | 0 | `NO_PLAUSIBLE_TYPE` | unclassified |

The typed unit restores exact source-owned values and refs, passes the existing
canonical validator, and materializes with the existing deterministic ID and
provenance contract. The model contributes only one opaque local type key.

The safe human trace pack contains four views:

1. unique safe typed path;
2. multiple plausible types;
3. plausible type with no exact constructible option;
4. false-singleton trap.

Each view shows what the model saw and did not see, the frozen response,
restored keys, code reason, validator/materializer result or fail-closed
disposition, and exact replay. Trace-pack integrity:
`b7112aa3666e50a7f6739ba3d12a31bc3deba6b3c8cba046f1cc8956169d33ee`.

## 6. False-singleton comparator

One structurally real case demonstrates the failure mode: a mechanical legacy
filter hides competitors and exposes a singleton, while the full Pack-backed
card set preserves plural ambiguity or blocks typing. The genuinely unique
case types only with one exact restored option.

```text
false_singleton_cases_total = 1
false_singleton_detected_total = 1
false_singleton_typed_total = 0
unsafe_typed_total = 0
wrong_singleton_total = 0
provider_calls_total = 0
```

## 7. Completeness and replay

```text
total_units = 3
typed = 1
unclassified = 2
no_fact = 0
unsupported = 0
technical_failure = 0
excluded = 0
unaccounted_units = 0
```

The existing V6 evidence authority rebuilds the package, Pack, request,
mapping, response, restored decisions, validation, materialization, and hashes
without provider access. The canonical evidence replay is exact; all four safe
trace views bind to exact replay. Six resealed tamper families fail closed,
including response/local-key substitution, source-ref loss/substitution,
package mutation/order, mapping order, and Pack mutation.

- Execution integrity:
  `6399c69d8d4453d9a5cabae80ffcff2d14cc2203f5f792edb8c7bf42f72acddf`.
- `replay_exact = true`.
- `replay_hash_match = true`.
- Replay hash mismatches accepted: `0`.
- ArtifactStore/ArtifactResolver exact round-trip: passed.

## 8. Anti-duplication and inactivity

Executable tests prove one product semantic owner, one Pack authority, one
response parser owner, one canonical validator, one canonical materializer,
and one V6 evidence/replay owner. They also prove:

- product reachability of the proof is false;
- provider reachability is false;
- all three generated Function bundles omit the proof module and symbols;
- Pipe/Action imports and behavior are unchanged;
- historical `source_fact_selection_v3` remains contained;
- PR #232 and GOAL 17 synthetic source projection are not imported;
- Gate 3/4 imports are unchanged;
- no regex/synonym shortlist, semantic subagent, new canonical type, or second
  canonical shape exists.

## 9. Tests, review, CI, and merge

Pre-merge local evidence:

- focused regression: `75 passed, 2 skipped`;
- full suite: `2290 passed, 5 skipped, 5 warnings`;
- independent full suite after `--cache-clear`:
  `2290 passed, 5 skipped, 5 warnings`;
- privacy plus Function-bundle tests: `16 passed`;
- KT2 corpus/proof builders and historical builders: all `--check` passed;
- mandatory Ruff and full Ruff on changed Python files: passed;
- `compileall`, privacy/integrity, `git diff --check`, and exact three-bundle
  rebuild: passed;
- new skips: `0`; generated bundle diff: `0`.

PR #241 received an explicit agent boundary review. It found no blocking issue
and did not claim independent human approval. GitHub `broker-reports-ci`
completed `SUCCESS` in 6m09s before merge.

## 10. Post-merge verification and live parity

Stage Q first passed on implementation merge `16fe3d2b...`. The closure-state
test then exposed its stale pre-KT2-only assertion. Per the corrective rule,
Stage Q was repeated in full on exact
`main == origin/main == 24948360095a749e11b1b0bcedbb8ae871a6b7f8`:

- focused suite: `213 passed, 5 warnings`;
- corpus builder: 1 real package, 3 real units, 0 customer values in Git;
- proof builder: 4 traces, 0 provider calls, 0 unaccounted units;
- full suite: `2290 passed, 5 skipped, 5 warnings`;
- all three generated bundles rebuilt with zero Git diff;
- proof module/schema/symbol search in all three bundles: absent;
- fresh read-only live delivery verifier: `PASSED`;
- live Functions: 3/3 exact; managed Prompts: 12/12 exact; repository factory
  boundary: passed.

Repository/live hashes:

| Function | Repository SHA-256 | Live SHA-256 |
| --- | --- | --- |
| Gate 1 | `a685e1c9e9be474e24c32d49821e59d384b1cc7a35f5a176e102c67df3e836af` | same |
| Gate 2 source | `aa49f3be808837ab41189644c5309478b82643dc5b77a97e84c581bdeb07eef8` | same |
| Gate 2 domain | `21ab2062cbf86a10404b22a7fb35cb745482b2b09e639ec695c5b3b2ef629ace` | same |

Because generated bundle bytes did not change and live hashes are exact, the
proof code is absent from live bundles and no live deploy is required. The
atomic release verifier was not rerun because there was no release candidate
or live mutation; the prior governed atomic receipt remains the operational
authority.

## 11. Privacy and change accounting

```text
provider_calls = 0
customer_documents_added_to_git = 0
customer_values_added_to_git = 0
raw_provider_payloads_added_to_git = 0
product_reachability_changes = 0
runtime_route_changes = 0
openwebui_core_changes = 0
managed_prompt_changes = 0
valve_changes = 0
production_admission_changes = 0
live_changes = 0
gate3_changes = 0
gate4_changes = 0
new_canonical_fact_types = 0
removed_canonical_fact_types = 0
canonical_type_count_delta = 0
canonical_shape_delta = 0
materializer_contract_delta = 0
canonical_materializer_count_delta = 0
```

Type Card metadata change: a versioned inactive model-facing projection was
added for existing Pack types. It changes no canonical meaning or Pack bytes.
Historical reports and receipts were not rewritten. Two historical builders
were corrected so later owner evolution is accepted only when exact successor
hashes are bound by the inactive KT2 contract; their historical outputs remain
byte-immutable.

## 12. Closure

Evidence PR: #243. This report becomes terminal only after that PR is merged;
the evidence merge commit is reported in the terminal response because a
commit cannot contain its own future merge hash.

```text
KT2_SAME_SOURCE_TYPE_FIRST_PROOF = PASSED
ONE_PRODUCT_SEMANTIC_ROUTE = TRUE
ONE_CANONICAL_MATERIALIZER = TRUE
FALSE_SINGLETON_OBSERVABILITY = PROVEN
TYPE_FIRST_PRODUCT_REACHABILITY = FALSE
PROVIDER_CALLS = 0
LIVE_CHANGES = 0
KT2 = COMPLETE
MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
