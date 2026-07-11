# Broker Reports Gate 2 Cross-Domain Candidate-Binding Research

Date: 2026-07-11

Status: `GATE2_CROSS_DOMAIN_CANDIDATE_BINDING_RESEARCH_READY`

## 1. Decision

The successful `cash_movement` proof contains a valid general mechanism, but
its legacy representation combined semantic fields with mechanically exact
values too early. The safe generalization is:

```text
bounded normalized row
-> shared deterministic candidate discovery
-> broker_reports_source_value_candidate_set_v0
-> shared deterministic relation discovery
-> broker_reports_candidate_relation_set_v0
-> one domain binding profile
-> package-bound strict provider JSON Schema
-> model selects ids, roles, and relations
-> deterministic binding materializer
-> existing domain finalizer
-> unchanged strict source-fact validator
-> deterministic stitcher
```

This is a shared kernel with narrow domain profiles, not nine discovery
implementations and not one unconstrained all-domain prompt.

The mechanism remains opt-in. Contract research and local proof do not by
themselves authorize a broad default switch or multi-domain live expansion.

## 2. Evidence inspected

The decision is based on the current runtime and these canonical evidence
sources:

- `OPENWEBUI_BROKER_REPORTS_GATE2_LIVE_AGENTIC_TABLE_ANALYSIS.report.md`;
- `BROKER_REPORTS_GATE2_LIVE_AGENTIC_TABLE_ANALYSIS_REFINEMENT.md`;
- `OPENWEBUI_BROKER_REPORTS_GATE2_BOUNDED_TABLE_DOMAIN_EXTRACTION.report.md`;
- normalized table projection and reconstruction-quality contracts;
- source-fact extraction, facts, domain extractor, prompt, and routing
  contracts;
- current package builder, provider-schema projection, finalizer, strict
  validator, stitcher, and managed Prompt registry;
- `gate2_candidate_binding.py` and
  `gate2_candidate_binding_runtime.py`.

The proven real native and PDF result was narrow: one selected row, one
`cash_movement` domain, a strict provider output, one validator-passed fact,
complete coverage, and zero Knowledge/RAG/vector/document deltas.

## 3. Original contract gap

The native cash row contained separate debit/credit decimal cells under
composite headers. The structural layer conservatively exposed some headers as
`unknown`. The legacy deterministic candidate builder recognized exact
date/amount/currency/quantity/instrument headers generally, then added a
`cash_movement`-only rule for checksum-reproducible decimals under unknown
headers.

The provider schema and finalizer could bind exact values and refs, but their
contract still described the model result as source facts. The legacy
finalizer could also fill a sole field candidate or attach a ref to one exact
model-returned value. This passed the bounded cash vertical without weakening
the validator, but it did not express:

- candidate identity independently from a fact field;
- an explicit semantic role chosen by the model;
- equal-value/different-ref ambiguity;
- mechanically supported multi-value relations;
- a common policy for all domains.

The new contract closes that gap by making candidate/role/relation selection a
first-class intermediate output.

## 4. Answers to the twenty contract questions

### 1. Which successful cash-binding parts are domain-neutral?

These parts are domain-neutral:

- narrow-package scope and stable row/cell/source-value refs;
- deterministic source-value resolution and checksum verification;
- exact normalization rules;
- stable opaque candidate ids and set hashes;
- package-bound strict provider schema;
- private raw output persistence;
- deterministic copying of a selected exact value and existing refs;
- independent final source-fact validation;
- issue carry-forward, row ownership, coverage, and stitch checks;
- no Knowledge/RAG/vector/document writes.

They belong in one shared candidate-binding kernel/runtime.

### 2. Which parts were embedded as `cash_movement` special cases?

The concrete special case is in the legacy
`_deterministic_value_candidates`: only `cash_movement` retained every
reproducible decimal under an `unknown` header as an `amount` candidate using
`cash_movement_unknown_decimal_candidate_v0`.

The broader legacy shape also coupled a candidate directly to a normalized
field and allowed the finalizer to fill one sole field candidate or match a
model-returned value to one candidate. That logic is not cash-only in code, but
the accepted evidence proved it only for cash and did not model semantic roles
or relations. It therefore could not be treated as a proven cross-domain
contract.

### 3. Which source-visible value kinds are mechanically discoverable?

With current exact normalizers and bounded table structure:

```text
decimal_amount
date
currency_code
quantity
instrument_identifier
instrument_label
explicit_fx_rate
short_visible_label
categorical_direction
source_provided_total
unknown_mechanical_value
```

Discovery means reproducible source syntax and structure only. It does not mean
the value's business role is known.

### 4. Which semantic roles require genuine model judgment?

Any assignment not mechanically stated by the source structure requires model
judgment within a profile. Examples include movement amount among debit/credit
cells, income subtype, fee versus tax, gross versus net, base versus quote,
trade price versus gross amount, trade versus settlement date, position
valuation versus another amount, and whether a row is the typed domain fact or
`unknown_source_row`.

The model selects from exact candidates. It does not normalize or invent the
underlying value.

### 5. Which domains require only independent value selection?

For the v0 minimum acceptance contract:

- `cash_movement`, `income`, `fee_commission`, and
  `document_summary_evidence` can be accepted through independent candidate
  selections;
- `position_snapshot` can use independent selections with one required
  instrument plus at least one quantity/valuation candidate;
- `trade_operation` v0 also validates independent selected roles, although
  same-row and quantity/instrument relations are valuable control evidence and
  its composite proof remains mandatory;
- `unknown_source_row` selects no values.

Independent selection does not waive source refs, checksums, required roles, or
coverage.

### 6. Which domains require candidate groups or relations?

The current profiles require:

- `withholding_tax`: `amount_with_currency`;
- `currency_fx`: `base_quote_amount_currency_group`.

The kernel also produces `same_row_candidate_group` for every multi-candidate
row and `quantity_with_instrument` where mechanically present. These are
optional structural evidence for position/trade in v0. Explicit income-tax and
operation-fee linkage would require a later mechanically proven relation kind;
it must not be inferred from proximity alone.

### 7. When may one candidate be assigned to more than one fact field?

Only when the active profile explicitly authorizes every involved role in
`candidate_reuse`. No shipped v0 profile does so. A relation containing a
candidate is not reuse authorization.

### 8. When must candidate reuse be forbidden?

Reuse is forbidden by default and whenever it would assign different semantic
meanings, duplicate a role/field, hide a missing candidate, or alias one source
cell as two independent source-visible values. Current profiles always fail
closed on reuse.

### 9. How do equal visible values from different cells remain distinguishable?

The candidate id includes package, row, cell, source-value ref, kind, and
reproduced value. Equal values in different cells therefore retain different
ids and refs. They are not deduplicated by value.

### 10. How is equal-candidate ambiguity represented?

Same-row candidates with the same kind and normalized value but distinct
source refs share an `ambiguity_group_ref` and the reason code
`equal_value_distinct_source_refs`. The model must choose an exact id and list
the group in `resolved_ambiguity_group_refs`. Missing explicit resolution fails
with `candidate_binding_ambiguity_unresolved`.

### 11. How may composite headers contribute evidence?

They may produce bounded `safe_header_descriptors`, header refs, column order,
and mechanical kind hints. They cannot assert a business role. An `amount`
descriptor may support numeric candidacy; it cannot decide debit/credit,
gross/net, fee/tax, or base/quote. PDF headers remain structural candidates and
never become semantic table truth.

### 12. Which fields may the finalizer safely materialize?

Only fields already selected by the model and allowed by the profile:

- selected normalized date, amount, currency, quantity, rate, converted
  amount, identifier, or label;
- selected bounded extracted-field refs/labels and subtype-safe tokens;
- common amount/date/currency/quantity/instrument objects derived from those
  selected normalized fields;
- existing row/cell/value/evidence refs;
- package-fixed audit, issue, completeness restriction, and downstream false
  flags;
- deterministic ids and pending validation placeholders.

The strict validator re-resolves and reproduces all value refs afterward.

### 13. Which choices must the finalizer never make?

It must never choose a candidate, role, field, relation, subtype, or fact type;
pick between equal candidates; infer gross/net, base/quote, fee/withholding,
trade/settlement, income linkage, or consolidation; repair a missing semantic
selection; resolve an issue; create an additional fact; or hide a row.

### 14. How should provider JSON Schema constrain dynamic ids?

Generate one strict schema from the exact package. Bind set ids/hashes and
package id with `const`. Represent each allowed
`(fact_field_path,candidate_id,semantic_role)` as a strict `anyOf` variant. Bind
relation ids and ambiguity refs to row-local enums, and bind domain/subtype to
profile enums. Use `additionalProperties=false` and bounded arrays. Do not put
raw candidate values into the output schema.

Post-call validation remains mandatory because provider schema is not the
final authority.

### 15. How should budgets prevent schema/context explosion?

The default hard budgets are 96 candidates and 128 relations per narrow
package. Exceeding either budget fails package construction with a typed code.
There is no truncation, sampling, or silent candidate/relation loss. The safe
remedy is a smaller validated source unit and a new package, not mutation of
the existing package.

### 16. How should repair preserve the original choices?

Repair uses the unchanged package, candidate set id/hash, relation set id/hash,
profile, selected refs, and package-bound schema. Initial and repair raw outputs
remain separate private artifacts. The model may revise only its selection.
Any changed identity/hash fails with `candidate_binding_contract_mismatch`.

### 17. How should unknown and null behave?

Optional typed fields with no valid candidate are simply not selected and
remain null/empty after materialization. Missing required roles reject a typed
selection.

When the domain cannot be supported safely, the model emits
`unknown_source_row` with no bindings or relations, a required uncertainty
code, low/none confidence, and uncertain/blocked completeness. Structural
non-fact rows use explicit `no_fact_results`. Neither form may silently omit a
selected ref.

### 18. What caused the current `currency_fx` rejection?

The retained safe report proves that the live all-domain run produced strict
private outputs, accepted eight packages, rejected `currency_fx`, and left one
uncovered ref. It does not retain the exact private model output or a safe typed
validator code in the report, so a more specific historical error must not be
invented.

Architecturally, the legacy contract exposed independent field candidates but
did not encode one package-bound base/quote amount-currency group or require
the model to select that relation. That is a relation-contract gap layered on
top of a value-role contract gap. The uncovered ref is the downstream coverage
effect of package rejection, not the root cause. There is no evidence that the
rejection was a provider outage: provider errors occurred only in later
retests and must remain a separate class.

The v0 correction therefore requires four exact role selections plus
`base_quote_amount_currency_group`; synthetic proof must still show whether
that fully closes the observed behavior.

### 19. Which second simple live domain is the best target?

`income` is the better second target. A bounded native/PDF income vertical was
already exercised in the preceding table-domain work, and the minimum profile
requires only one exact amount. It isolates cross-domain generality with less
structural risk. `position_snapshot` requires an instrument plus quantity or
valuation and is a useful later structural relation test, but a worse first
control.

### 20. Which composite domain is the hard target?

`currency_fx` is the preferred hard target because it exercises two amounts,
two currencies, optional explicit rate/date, role asymmetry, a required
relation, and the previously rejected domain. `trade_operation` remains a
separate mandatory composite synthetic proof because it exercises direction,
instrument, quantity/amount, date, price, and fee without finalizer role
assignment.

## 5. Responsibility matrix

| Component | Owns | May do | Must not do | Fail-closed evidence |
| --- | --- | --- | --- | --- |
| Candidate discovery | Mechanical value inventory and stable ids | Resolve existing source refs, reproduce exact values, attach structural evidence and profile allowlists | Choose semantic roles, invent/convert values, cross package scope, silently truncate | Candidate set id/hash, reason codes, budget error |
| Relation discovery | Mechanical group inventory | Group existing candidates by proven same-row structure and declare exact cardinality | Assign business meaning, link facts from proximity, edit candidates | Relation set id/hash, validation status, budget error |
| Package builder | Narrow source/profile/schema boundary | Attach the candidate set, relation set, profile, output contract, issue and coverage constants | Widen refs, reinterpret legacy packages, switch all domains by default | Package validation, exact scope and mode |
| LLM | Semantic selection within one domain profile | Select candidate/role/field triples, relation ids, subtype, unknown/no-fact, uncertainty/confidence/completeness | Return free-form values, mint refs/relations, reconstruct table, decide ownership, tax, consolidation, or Gate 3 | Private strict raw output bound to package schema |
| Binding materializer/finalizer | Deterministic projection of a validated selection | Copy selected values/refs and package-fixed audit/issue/restriction data; construct common objects | Select or replace semantic choices, resolve ambiguity/issues, create facts beyond output, hide coverage | Binding validation plus pending finalized candidate |
| Strict validator | Final source-fact authority | Re-resolve refs/checksums, reproduce values, check domain/field/role/relation/reuse/ambiguity/issue/audit/coverage | Trust provider schema alone, accept failed binding, weaken source-fact rules | Typed validation artifact and accepted/rejected ids |
| Stitcher | Deterministic final row ownership | Merge only validator-passed domain artifacts and compute coverage/conflicts | Reclassify facts, repair rejected packages, drop uncovered/conflict refs | Complete/partial stitch, uncovered and conflict refs |

## 6. Contract boundaries

The new private contract family is:

```text
broker_reports_source_value_candidate_set_v0
broker_reports_candidate_relation_set_v0
broker_reports_domain_candidate_binding_profile_v0
broker_reports_candidate_binding_output_v0
broker_reports_candidate_binding_validation_v0
```

It composes with, rather than replaces:

```text
broker_reports_domain_extraction_package_v0
broker_reports_source_facts_v0
broker_reports_source_fact_validation_v0
broker_reports_domain_source_fact_stitch_v0
```

The candidate and relation payloads, raw outputs, and pre-validation facts are
private. Safe reporting is limited to opaque ids, types, roles, counts,
statuses, and reason/error codes.

## 7. Domain and ownership map

| Domain/profile | Minimum typed selection | Required relation | Main semantic risk |
| --- | --- | --- | --- |
| `cash_movement` | movement amount | none | debit/credit amount choice |
| `income` | income amount | none | subtype and gross/net meaning |
| `withholding_tax` | tax amount and currency | `amount_with_currency` | tax/income linkage and jurisdiction |
| `fee_commission` | fee amount | none | fee subtype and operation linkage |
| `position_snapshot` | instrument plus quantity or valuation | none | position versus transaction meaning |
| `trade_operation` | direction, instrument, quantity or amount | none in v0 | price/amount/fee/date role assignment |
| `currency_fx` | base/quote amounts and currencies | `base_quote_amount_currency_group` | base/quote and rate role assignment |
| `document_summary_evidence` | source-provided summary value | none | calculated versus source-provided total |
| `unknown_source_row` | no bindings | none | silent omission |

## 8. Migration decision

The migration is explicit and reversible:

1. `candidate_binding_enabled=false` remains the default.
2. Opt-in packages carry
   `candidate_binding_mode=candidate_ids_and_semantic_roles_v0` and all three
   package-side contracts.
3. Those packages use `broker_reports_candidate_binding_output_v0`.
4. Packages without the mode remain on the legacy strict source-fact output.
5. Persisted legacy artifacts are immutable and are never reinterpreted in
   place.
6. A default switch requires the specified local and live proof gates; contract
   availability alone is insufficient.

## 9. Validation plan

The minimum proof sequence is:

1. Negative matrix: foreign ids, forbidden fields/kinds/roles, reuse,
   equal-value ambiguity, missing/invalid/cross-row relations, missing roles,
   issue-limited completeness, coverage gaps, and unchanged-set repair.
2. All nine profiles through the same package, binding materializer, existing
   finalizer, strict validator, and stitch path.
3. Real native and PDF cash regression through candidate ids.
4. One real bounded `income` typed fact; unknown-only does not pass.
5. Synthetic live-provider `currency_fx` with two amount/currency pairs,
   optional explicit rate, selected relation, exact refs, and complete coverage.
6. Synthetic trade composite with model-assigned roles and no finalizer role
   inference.
7. Artifact/private persistence and zero Knowledge/RAG/vector/document deltas.

Provider availability errors are counted separately and do not justify
contract mutation.

## 10. Risks and deferred work

- The current candidate discovery implementation is table-row based; bounded
  text-segment discovery requires a separately versioned mechanical builder.
- Future explicit income-withholding, operation-fee, unit-price, currency-pair,
  and section-total relations need source-structural proof before admission.
- `trade_operation` relations are optional in v0; composite proof may justify a
  later profile version, but should not be anticipated speculatively.
- No live result should be claimed from local tests, and no provider incident
  should be reported as semantic rejection.
- Broad mixed-table or cross-document expansion remains outside this slice.

## 11. Non-goals

No OpenWebUI core patch, ordinary processed upload, Knowledge/RAG/vector load,
OCR/VLM, page rendering for extraction, Gate 3 ledger, tax calculation,
declaration generation, spreadsheet generation, cross-document consolidation,
or customer-visible raw source content is part of this contract.
