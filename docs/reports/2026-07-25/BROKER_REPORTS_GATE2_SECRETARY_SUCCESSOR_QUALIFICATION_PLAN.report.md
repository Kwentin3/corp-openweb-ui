# Broker Reports — Gate 2 Successor Qualification Plan

Дата: 2026-07-25  
Статус: `GOAL_10_QUALIFICATION_PLAN: COMPLETED`

## Qualification subject

Квалифицируется точный bundle, не модель в изоляции:

```text
exact model ID
+ provider route revision
+ canonical financial decision contract hash
+ provider projection hash/transform ledger
+ Registry snapshot hash
+ deterministic scope package version
+ prompt hash
+ canonical validator/materializer revision
+ benchmark manifest hash
```

Target workload — existing `gate2_financial_evidence` на scopes, построенных напрямую deterministic source/domain preparation. Source/domain qualification labels не переносятся.

## Product invariants

Каждый case проверяет:

1. exact eligible `input_type_id`, когда тип однозначен;
2. literal source value preservation;
3. correct Registry role binding;
4. package ref membership;
5. ambiguity discipline;
6. unclassified value preservation;
7. zero invented values/IDs;
8. zero duplicate value bindings;
9. zero cross-row/out-of-scope bindings;
10. strict branch conformance;
11. complete terminal ownership;
12. deterministic context projection.

Не проверяются как primary model metrics:

- internal fact paths;
- candidate/relation graph topology;
- relation count;
- subtype decoration;
- confidence/completeness;
- free uncertainty wording;
- audit/system IDs.

## Synthetic fixture families

| Family | Product invariant | Допустимый equivalence set |
|---|---|---|
| signed/precision literal | bytes/semantic string не меняются | один ref, typed либо unclassified по definition |
| currency/date | оба refs сохранены и roles совместимы | eligible typed или explicit unclassified |
| repeated header/layout | не создаётся financial input | bounded no-financial reason |
| detail vs subtotal | выбран requested detail scope | no subtotal/cross-row binding |
| missing optional date | null/absence не заполняется | typed, если required roles есть |
| equal visible values | сохраняется identity exact source ref | только package-requested ref |
| adjacent FX values | пары amount/currency не смешиваются | Registry-compatible role assignment |
| multiple hypotheses | безопасный type либо unclassified | никакой guessed alternative |
| forbidden neighbour | forbidden refs zero | только allowed scope |
| explicit unclassified | все финансовые values сохранены | unclassified reason set |
| unsupported shape | explicit unsupported | никакого fallback/repair |

Fixture хранит invariant и допустимые semantic outcomes, а не только один expected internal JSON.

## Порядок gates

### Q0 — deterministic contract tests

- package integrity;
- enum generation;
- provider projections;
- canonical parsing;
- materializer/context determinism;
- compatibility readers;
- no provider calls.

Gate: 100% pass, stable hashes, no system fields в model output.

### Q1 — synthetic secretary fixtures

- local fake model payloads;
- positive/negative branch coverage;
- semantic equivalence comparator;
- mismatch paths обязательны.

Gate: все product invariants, intentional negative cases rejected.

### Q2 — exact-model provider schema probe

- один bounded non-customer schema call на exact published model;
- verify requested/resolved ID;
- no fallback/repair;
- canonical revalidation после provider.

Gate: transport + adapted schema + canonical parse all pass.

### Q3 — bounded non-customer semantic run

- frozen synthetic corpus;
- strict per-operation budget;
- actual provider output не коммитится;
- safe value-free receipt.

Gate: canonical 100%, literal/ref 100%, inventions/duplicates/cross-row 0, unclassified loss 0.

### Q4 — bounded actual-corpus shadow

- отдельная authorization;
- customer-facing routing не меняется;
- legacy/successor outputs раздельны;
- product-invariant diff.

Gate: no literal/provenance/terminal-coverage regression; explicit disposition for every selected ref.

### Q5 — full Gate 2 scope shadow

- frozen full-scope baseline;
- no Gate 3;
- call/cost/latency and failure layer accounting;
- repeatability.

Gate: coverage ≥ baseline, unclassified loss 0, context integrity parity, calls/cost within approved policy.

### Q6 — production admission

Отдельный release program после Q5. Dual-read/successor single-write, rollback drill, observation window.

## Comparator output

Каждый failure получает:

- `failure_layer`: package/schema/provider/canonical/semantic/materialization/context;
- `mismatch_paths`: value-free;
- `classification`: model_wrong, acceptable_alternative, comparator_defect, contract_gap, actual_data_loss, unknown;
- `affected_source_refs_total`;
- `literal_loss_total`;
- `terminal_ownership_gap_total`.

`UNKNOWN` не допускается к production admission, но не автоматически дисквалифицирует модель до diagnostic closure.

## Stop rules

- provider output accepted, canonical rejected;
- any out-of-package/invented/cross-row ref;
- any authoritative literal/provenance loss;
- unclassified converted to no-financial;
- hidden repair/fallback;
- Registry expansion proposed to make fixture green;
- exact internal graph equality снова стала primary metric;
- actual corpus authorization отсутствует.

## Acceptance

- `BENCHMARK_MEASURES_PRODUCT_ABILITY: YES`
- `INTERNAL_STRUCTURE_EXACTNESS_AS_PRIMARY_METRIC: ZERO`
- `QUALIFICATION_GATES: Q0_THROUGH_Q6_DEFINED`
- `CURRENT_PROVIDER_CALLS: ZERO`
- `CURRENT_MODEL_QUALIFICATION_CHANGE: ZERO`
