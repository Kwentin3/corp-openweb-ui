# Broker Reports Gate 5 Stable Income-Group Tax Base v0

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.22_CLOSED`

Proof outcome: `PROVEN_WITH_REPLAY_COMPILER_LIMITATION`

Product status: `INACTIVE PROOF`

Date: 2026-08-10

## Purpose

This contract closes only the declaration-driven
`section2_calculation_behavior_missing` boundary. It publishes one trusted,
versioned and deterministic stable tax semantic between a complete G5.14
securities category model and a future declaration projection:

```text
complete category Tax Model
+ explicit whole-income-group facts
+ exact group-completeness assertion
+ hash-pinned methodology
        -> existing execute_published_typed_behavior_v1
        -> stable income-group Tax Base Model
```

It does not publish a Section 2 projection, an income-group/form-code mapping,
an XML/PDF document, a tax rate or calculated tax.

## Backward requirement reconstruction

The official FNS procedure for order `ЕД-7-11/913@` states that Section 2 is
calculated separately for each income group. For the relevant group it
requires total income, non-taxable income, taxable income, deductions,
accepted expenses and tax base. Paragraphs 40-46 define the subtraction and
reduction relationships. The official order applies beginning with the 2025
tax period.

Sources were verified on 2026-08-10:

- [official FNS order page](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/);
- [official procedure DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx), 106008 bytes, SHA-256 `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc`.

The backward classification is:

| Meaning | Owner/provenance |
| --- | --- |
| complete securities category gross income and allowable expenses | source-tagged G5.14 Tax Model, ultimately Financial Case/Supplemental evidence plus methodology decisions |
| other income in the same stable tax group | explicit `user_verified_fact`, including explicit zero |
| other allowable expenses in the same stable tax group | explicit `user_verified_fact`, including explicit zero |
| non-taxable group income | explicit `user_verified_fact`, including explicit zero |
| tax deductions reducing this group | explicit `user_verified_fact`, including explicit zero |
| taxpayer status | explicit `user_verified_fact` checked against methodology applicability |
| whole-group coverage | separate `user_verified_fact` bound to the exact category and group-context hashes |
| total income, taxable income, accepted expenses and tax base | `methodology_derived` |
| tax period, applicable category, currency and stable income-group semantic | immutable methodology applicability |

No rate or external case-time reference fact is needed to stop at tax base.
The official procedure remains methodology authority evidence; it is not
silently converted into a case fact.

## Existing capability basis

No sixth primitive is introduced. The existing basis remains exactly:

```text
RESOLVE / ACQUIRE / EXECUTE / AGGREGATE / PROJECT
```

The new behavior is a third static registration under the unchanged
`execute_published_typed_behavior_v1` capability. The v0/v1 capability
resources and five-family model projection remain byte-for-byte unchanged.

Exact identity:

```text
methodology_id       ru-ndfl-securities-tax-model-proof
methodology_version  2026.2-experimental
behavior_id          securities_income_group_tax_base_v0
input_contract       broker_reports_gate5_income_group_tax_base_input_v0
output_contract      broker_reports_gate5_income_group_tax_base_model_v0
```

The methodology package resource is:

```text
gate5_tax_methodology.ru_ndfl_securities_income_group_tax_base_proof.v0.json
sha256 56bcc7554c69757623a67497aa728cefc662e8c08a5795dfcb5562da1559bb80
projection_sha256 234e02c5e1a45cba7bd0e89178cebbbbfb4f517dc48a1be7ce5d47fc20e1f099
```

G5.8 owns immutable resolution/hash verification. G5.18 owns exact static
behavior and input/output dispatch. G5.14 owns category-model validation. The
new `Gate5IncomeGroupTaxBaseRuntimeFactory.create` owns only the stable tax
calculation and its output validation.

## Closed input and completeness binding

The behavior input contains exactly:

```text
category_tax_model
taxpayer_status
group_values:
  other_group_income
  other_group_allowable_expenses
  non_taxable_income
  tax_deductions
completeness_evidence
```

Every group value is a non-negative two-decimal money value with
`user_verified_fact` provenance. Omission is not equivalent to zero.

`describe_input` validates the category model and explicit context, then
returns canonical hashes for the category model, group context and their
combined input binding. Completeness evidence must state
`all_income_and_reductions_in_stable_income_group` and bind to that exact
combined hash. Any value/category mutation makes the old evidence stale.

The public G5.14 `validate_category_model` method revalidates the category
schema, scope/member binding, category completeness evidence, aggregate
arithmetic, member provenance, loss state and operation-methodology binding.
The G5.22 runtime does not reconstruct those rules.

## Deterministic semantic result

For this published behavior the stable result contains:

```text
total_income
taxable_income
accepted_expenses
tax_base
```

The code-owned behavior applies Decimal arithmetic to the methodology-defined
semantic relationships:

```text
total_income = category gross income + other group income
taxable_income = total income - non-taxable income
accepted_expenses = category allowable expenses + other group allowable expenses
tax_base = taxable income - tax deductions - accepted expenses
```

It rejects non-taxable income above total income and deductions plus accepted
expenses above taxable income. It does not clamp, infer zero or manufacture a
negative tax base.

The output retains the complete validated category snapshot, all explicit
group facts and completeness evidence, exact input/methodology hashes, and a
`methodology_derived` record for every calculated value. The same owner
deterministically rebuilds and validates any registered output, so result
tampering fails at the typed-execution boundary.

## No declaration hardcode

The runtime contains no Section 2 identifier, form-line identifier, income
group code, income-type code, XML path, XSD name, PDF coordinate, rate or
threshold. Concrete period, taxpayer status, category, currency and stable
group applicability live only in the immutable methodology resource and are
read as closed data.

The four equations remain local ordinary behavior code because the current
runtime has no safe generic expression evaluator and G5.22 does not justify a
DSL/rules engine. Adding a dynamic formula language would be larger and less
trustworthy than this one reviewed behavior. A tax-rule change therefore
requires a new methodology/behavior version and reviewed code binding; an XML
or form-line change does not require changing this runtime.

## Representative proof

The positive test uses the real public chain:

```text
two Gate 4-backed source scopes
-> two G5.13 operation models through typed EXECUTE
-> G5.14 complete category through AGGREGATE
-> G5.22 behavior through the same typed EXECUTE
```

Representative values:

```text
category gross income       150.00 RUB
category allowable expense  100.00 RUB
other group income           10.00 RUB
other group expense           4.00 RUB
non-taxable income             5.00 RUB
tax deductions                3.00 RUB
total income                 160.00 RUB
taxable income               155.00 RUB
accepted expenses            104.00 RUB
tax base                      48.00 RUB
```

Retained source kinds are Financial Case, Supplemental Fact,
user-provided supplemental evidence, proof assumption, user-verified fact and
methodology-derived result.

Meaningful fail-closed proofs cover missing/stale completeness, missing group
values, unsupported taxpayer status, incompatible currency, excessive
non-taxable income/reductions, contract mismatch, output mutation and package
resource hash drift. A package-copy test proves import/resource operation
without workspace-only dependencies.

## History-free authoring replay

The historical G5.21 payload remains exact at 24971 bytes and its original
hash. The additive replay owner freezes a separate 26614-byte payload:

```text
resource  gate5_declaration_authoring_language.primary.g522.payload.json
sha256    cd186b746aabbe699820e4ec58bd08a8cfd1e7041de373af0d4d2ee971267736
history   none
bias      passed, disallowed hits zero
```

Only the repository-truth inventory changed from `2026.1-proof` to
`2026.2-proof` by appending the real new methodology. Runtime capabilities and
official evidence are exact G5.21 parity. The payload contains no previous
candidate, validator error, expected next gap or goal history.

One new ephemeral read-only `gpt-5.6-sol` inference produced one unchanged
17613-byte candidate (SHA-256
`dee9cec002449e31ae7536a36e1a897fe2df1c7355f65ec999c7723cf5d70bf2`).
It used `securities_income_group_tax_base_v0`, did not emit
`section2_calculation_behavior_missing`, and independently named
`gap.singleton_category_aggregation` as the first blocker.

That finding is real: the current G5.14 closed contract rejects fewer than two
members even when a one-operation category scope has exact user-verified
completeness. G5.22 records it but does not change G5.14.

Replay limitation: plain JSON parsing and the closed schema passed, but the
unchanged candidate later used the PROJECT capability with an empty artifact
list inside a different unsupported projection requirement. The existing
compiler rejected it at `requirements[6].compositions[1]`. No repair,
follow-up or retry was performed. Therefore this goal claims successful
independent disappearance/rediscovery of the first blocker, not a second proof
that every independently authored candidate compiles.

## Boundary and next dependency

`G5.22_CLOSED` means the original missing calculation behavior is implemented,
trusted and proven through the existing EXECUTE primitive. It does not mean a
taxpayer case is complete, a Section 2 projection exists or an electronic
declaration can be produced.

The next declaration-discovered blocker is:

```text
gap.singleton_category_aggregation
```

Known later dependencies remain observed only:

```text
Section 2 classification/projection artifact
full electronic declaration composition
```

No next slice is authorized by this contract.
