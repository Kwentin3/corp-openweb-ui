# Broker Reports Gate 2 Cross-Domain Candidate-Binding Refactor

Date: 2026-07-11

Final status: `GATE2_CROSS_DOMAIN_CANDIDATE_BINDING_PARTIAL`

Live blocker: `LIVE_CROSS_DOMAIN_PROOF_NOT_COMPLETE no_available_model_accepts_or_returns_strict_json_schema`

## 1. Result

The `cash_movement` exact-value refinement is now a shared opt-in candidate-
binding protocol for all nine Gate 2 source-fact domains. The model selects
opaque candidate ids, semantic roles, field paths and mechanically discovered
relation ids. It no longer returns free-form source values in this mode.

The implementation, negative matrix and all-domain production-factory matrix
pass locally. The new closed-world bundle and nine managed domain Prompts are
installed live with candidate binding disabled by default. Multi-domain live
expansion is not authorized because the provider returned availability errors
before candidate-binding validation for every bounded live call.

## 2. Original gap and generalization

The proven cash rows contained several checksum-reproducible decimals under
composite or unknown headers. The legacy path attached mechanical candidates
directly to source-fact fields and had a cash-only unknown-decimal discovery
rule. It could prove the selected cash value/ref, but it had no independent
candidate identity, role choice, equal-value ambiguity or multi-value relation
contract.

The refactor introduces this shared flow:

```text
bounded normalized source unit
-> shared candidate discovery
-> broker_reports_source_value_candidate_set_v0
-> shared relation discovery
-> broker_reports_candidate_relation_set_v0
-> broker_reports_domain_candidate_binding_profile_v0
-> package-bound strict provider JSON Schema
-> model selects ids/roles/relations
-> binding validator and generic materializer
-> existing domain finalizer
-> unchanged strict source-fact validator
-> deterministic stitcher
```

The legacy `deterministic_value_candidates` path remains explicit for packages
without `candidate_binding_mode`. Persisted legacy artifacts are not mutated.

## 3. Contracts and profile matrix

The canonical contracts are:

- `BROKER_REPORTS_GATE2_SOURCE_VALUE_CANDIDATES.v0.md`;
- `BROKER_REPORTS_GATE2_CANDIDATE_RELATIONS.v0.md`;
- `BROKER_REPORTS_GATE2_DOMAIN_BINDING_PROFILES.v0.md`;
- `BROKER_REPORTS_GATE2_CANDIDATE_BINDING_OUTPUT.v0.md`.

Default hard budgets are 96 candidates and 128 relations per narrow package.
Overflow fails; candidates and relations are never silently truncated.

| Domain | Required binding | Required relation |
| --- | --- | --- |
| `cash_movement` | movement amount | none |
| `income` | income amount | none |
| `withholding_tax` | tax amount and currency | `amount_with_currency` covering those selected roles |
| `fee_commission` | fee amount | none |
| `position_snapshot` | instrument and quantity-or-valuation | none |
| `trade_operation` | direction, instrument and quantity-or-amount | none; same-row/quantity-instrument relations are optional v0 evidence |
| `currency_fx` | base/quote amounts and currencies | `base_quote_amount_currency_group` covering all four selected roles |
| `document_summary_evidence` | source-provided summary value | none |
| `unknown_source_row` | no value binding; explicit uncertainty | none |

## 4. Responsibility boundary

| Component | Owns | Must not own |
| --- | --- | --- |
| Candidate discovery | exact mechanical kinds, normalized value reproduction, existing refs/checksum refs, ambiguity groups | business role or fact field |
| Relation discovery | mechanically supported same-row groups | base/quote, gross/net, fee/tax or linkage meaning |
| Package builder | narrow scope, profile, versioned contracts and budgets | model choice or final ownership |
| LLM | candidate id + allowed role/path, relation id, subtype/uncertainty within schema | values, refs, relation definitions, issues or Gate 3 decisions |
| Binding validator | set integrity, source reproduction, role/field/domain, reuse, ambiguity, relation participation and coverage | repair or semantic defaulting |
| Materializer/finalizer | copy only selected package values/refs and insert package-fixed audit/issue constants | choose candidates, roles, relations or resolve ambiguity |
| Strict source-fact validator | final provenance/value reproduction, schema, issue, audit and coverage authority | accept failed bindings |
| Stitcher | final row ownership, conflicts and complete accounting | alter accepted facts or consolidate documents |

## 5. Implementation result

Implemented:

- shared kernel, stable ids/hashes and nine profiles;
- equal-value/different-ref ambiguity groups;
- same-row, amount/currency, quantity/instrument and FX group relations;
- dynamic strict provider schema containing ids and roles but no source values;
- generic fail-closed binding validator/materializer;
- exact candidate/relation set integrity and source-value/checksum-ref checks;
- required-relation participant checks, including the exact selected FX roles;
- unchanged final source-fact validator and stitcher route;
- private ArtifactStore records for candidate sets, relation sets and binding
  validations;
- explicit `candidate_binding_enabled=False` default in runtime/Pipe;
- candidate-binding mode in the nine repository-governed managed Prompt bodies;
- opt-in live proof flags for real table and all-domain synthetic scripts;
- closed-world bundled Function modules with no workspace import dependency.

The full-path matrix exposed and fixed one real mismatch without weakening the
validator: optional withholding country evidence initially targeted an
extracted refs field forbidden by the existing strict withholding schema. The
profile now uses the existing `normalized_values.label` plus
`original_value_refs.label` pair.

## 6. Local proof

### Negative and repair matrix

Fourteen typed negative cases cover foreign ids, forbidden role/field/kind,
reuse, coverage gap, issue-overstated completeness, missing/invalid/cross-row
relations, equal-value ambiguity, changed set identity, tampered normalized
value and tampered checksum ref. Candidate/relation budget overflow also fails
closed. Repair preserves candidate set, relation set and provider schema hashes.

### All-domain production-factory matrix

Command:

```text
py -3.11 -m unittest tests.test_broker_reports_gate2_candidate_binding -q
```

Result:

```text
Ran 9 tests in 1.451s
OK
```

For every one of the nine profiles, the proof ran the real package builder,
candidate-binding runtime, domain finalizer, unchanged strict validator and
stitcher against an isolated real SQLite ArtifactStore. Result: binding
accepted `9/9`, strict facts accepted `9/9`, complete stitch `9/9`, conflicts
`0`, uncovered refs `0`. The FX case selected the required four-part relation;
the trade case bound direction, instrument, quantity and amount. A positive
issue-limited cash case retained its issue ref/impact and stayed partial.

### Runtime, compatibility and closed-world regression

The dedicated runtime integration proves strict provider schema, private
candidate/relation/validation persistence, selected amount/ref reproduction,
validator pass and complete stitch. The full regression result was:

```text
Ran 181 tests in 22.834s
OK
```

Bundle tests passed `2/2`; candidate binding remains false by default. The live
Function content equals the local closed-world bundle:

```text
bc57b54b065be931d84c0f3b98a1d1a9cd4a5b931d7ca4f22c7ae334b7946792
```

All nine managed Prompt updates passed with strict structured output required.

## 7. Live proof and exact blocker

### All-domain synthetic provider run

Run: `sfdrun_7aebe1e364ecb97bcaff752c`.

- packages: accepted `0`, rejected `9`;
- provider errors: `9` (`1` in each domain);
- strict raw outputs: `9`; fallback outputs: `0`;
- source facts: `0`;
- candidate sets persisted: `9`; relation sets persisted: `9`;
- exact safe error: `gate2_model_provider_error=9`;
- the 80 synthetic artifacts were audited and purged.

This is a provider/transport failure before binding validation, not nine
candidate-contract rejections.

### DeepSeek strict structured-output control

Connected model: `deepseek-v4-pro`.

Run: `sfdrun_a8981d85cc1b1625f33b9a8b`.

- packages: accepted `0`, rejected `9`;
- exact safe error: `gate2_model_schema_response_format_rejected=9`, one in
  every domain;
- model-produced binding objects: `0`;
- source facts: `0`; fallback outputs: `0`;
- candidate sets persisted: `9`; relation sets persisted: `9`;
- Knowledge/vector/document/file deltas: `0`;
- all 80 synthetic artifacts were audited and purged.

DeepSeek was reachable, so this is not the GPT quota incident. Its current
OpenWebUI/provider connection rejects the required
`response_format=json_schema, strict=true` request before the model returns an
object. JSON mode or free-form parsing would weaken the accepted contract and
was not used. A real customer row was not retried because all nine synthetic
schemas already failed at the same pre-data boundary.

An isolated synthetic `response_format=json_object` control returned HTTP 200,
valid JSON and an exact three-field/nested-binding shape match. This proves the
connection can follow a simple JSON instruction, but JSON mode has no
package-bound schema enforcement and is not an accepted Gate 2 fallback.

### Real cash regression

The approved case preflight still found one bounded native and one bounded PDF
`cash_movement` target. The new-contract native attempt used `gpt-5.6-sol`:

```text
sfdrun_5bcd889970fe6c9479abb5d1
```

It produced one private strict raw-output artifact, no fallback and exactly
`gate2_model_provider_error=1`; accepted facts `0`, rejected packages `1`.
The PDF attempt was not repeated after the same provider incident was proven
across all nine domains. Therefore the prior native/PDF cash proofs remain a
legacy-baseline result and do not satisfy the new-contract regression gate.

### Second domain and composite targets

- `income`: no safe bounded real target in the approved case;
- `position_snapshot`: one eligible bounded real PDF target exists, but live
  execution was not repeated during the proven provider incident;
- `currency_fx`: no safe bounded real target exists in this case; the local
  relational proof passed, while live synthetic-provider execution failed on
  provider availability;
- `trade_operation`: no safe bounded real target exists; the required local
  composite production-factory proof passed.

Live candidate-binding totals in this pass are accepted `0`, rejected `19`:
provider/availability errors `10`, strict-schema capability rejections `9`,
candidate-contract validation errors `0`.

## 8. Persistence, privacy and no-RAG guards

Candidate and relation payloads are private case artifacts in
`project_artifact_payload`; only opaque ids, kinds/counts/statuses and safe
error aggregates appear in safe metadata. Successful local runtime proof also
persists private `broker_reports_candidate_binding_validation_v0` records.
Provider failures do not create accepted source facts or binding validations.

Both live runs proved these deltas:

```text
Knowledge rows = 0
vector collections/files/bytes = 0
document rows = 0
ordinary processed uploads = 0
fallback outputs = 0
```

No OCR/VLM, page rendering, tax calculation, declaration, XLS/XLSX or
cross-document consolidation was performed.

## 9. Decision

The cash-specific special case has been generalized in code and deterministic
proof. The opt-in runtime is safe for further bounded proofs, but broad default
activation and multi-domain live expansion are not yet safe. Required next
evidence is provider recovery followed by:

1. native and PDF cash regression through candidate binding;
2. the eligible real `position_snapshot` vertical;
3. all-domain synthetic acceptance on a provider that supports strict dynamic
   JSON Schema, especially `currency_fx`.

No contract mutation is justified by the current provider outage.

## 10. Proven statuses

```text
GATE2_CROSS_DOMAIN_CANDIDATE_BINDING_RESEARCH_READY
GATE2_SOURCE_VALUE_CANDIDATE_CONTRACT_READY
GATE2_CANDIDATE_RELATION_CONTRACT_READY
GATE2_DOMAIN_BINDING_PROFILES_READY
GATE2_CANDIDATE_BINDING_OUTPUT_CONTRACT_READY
GATE2_CANDIDATE_BINDING_RUNTIME_READY
GATE2_CANDIDATE_BINDING_VALIDATOR_READY
GATE2_ALL_DOMAIN_BINDING_MATRIX_SYNTHETIC_PASSED
TRADE_OPERATION_COMPOSITE_BINDING_PASSED
GATE2_ROW_COVERAGE_PROVEN
GATE2_SOURCE_VALUE_REFS_PROVEN
GATE2_ISSUE_CARRY_FORWARD_PROVEN
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
GATE2_CROSS_DOMAIN_CANDIDATE_BINDING_PARTIAL
LIVE_CROSS_DOMAIN_PROOF_NOT_COMPLETE no_available_model_accepts_or_returns_strict_json_schema
```

Not claimed:

```text
CASH_MOVEMENT_CANDIDATE_BINDING_REGRESSION_PASSED
SECOND_LIVE_DOMAIN_CANDIDATE_BINDING_PASSED
CURRENCY_FX_RELATIONAL_BINDING_PASSED
READY_FOR_MULTI_DOMAIN_LIVE_TABLE_EXTRACTION_PROOFS
```
