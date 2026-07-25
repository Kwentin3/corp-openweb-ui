# Broker Reports — Gate 2 ambiguity discipline, Goal 9A

Дата: 2026-07-25

Статус: `COMPLETED`

## Outcome

Реализован отдельный bounded source-context contract для successor model
input v2.

Context строится только из authoritative Gate 1 `model_source_projection` и
source values уже принятого deterministic scope v2. Он группирует значения
по исходной row/text association, но не передаёт модели внутренний group,
row, cell, segment, table, page, document или path identifier.

Typed admission остаётся code-owned и не зависит от этого context.

## New exact identities

- `broker_reports_gate2_financial_evidence_source_context_v2`;
- `gate2_financial_evidence_bounded_source_context_v2`;
- `broker_reports_gate2_financial_evidence_successor_model_input_v2`;
- `broker_reports_gate2_financial_evidence_successor_result_v2`.

Legacy model-input v1 remains explicit and unchanged. Runner selection between
v1 and v2 is configuration-owned; v2 fails closed without a matching context
package and deterministic scope v2.

## Provider-facing shape

Model input v2 contains only:

- Registry types admitted by Goal 8;
- ordered `source_groups`;
- required binding `source_value_ref`;
- authoritative literal and value type;
- allowed roles;
- bounded visible column meaning or visible label;
- bounded row/section semantic role.

Deterministic reference values remain bindable, but their internal locator
literal is projected as `null`.

Forbidden recursively:

- document/row/cell/segment/table/page/path refs;
- source locators and provenance;
- candidate/relation graphs;
- audit/confidence/uncertainty;
- expected answer;
- source family and internal package/scope identities.

The required `source_value_ref` is the only binding identity exposed.

## Limits and fail-closed rules

- at most 32 context groups;
- at most 128 source values;
- source literal at most 4096 characters;
- visible label/column meaning at most 160 characters;
- no truncation;
- every source value represented exactly once;
- every non-reference value requires visible Gate 1 association;
- Gate 1 literal must exactly match scope authority;
- integrity and scope identity revalidated before model input.

## Shared association authority

Typed admission and source-context projection now consume one shared
Gate 1 visible-association extractor. This removes duplicate row/header
interpretation code without changing admission policy, Registry meanings or
the accepted scope-v2 contract.

## Contracts changed

- new private source-context package/factory/validator;
- optional explicit model-input v2 path in successor runner;
- source-context v2 identity in successor result v2 safe summary;
- bundle closed-world module order;
- shared visible-association extraction used by typed admission.

## Contracts explicitly unchanged

- Gate 1 schemas and semantic authority;
- typed-admission schema/policy and predicates;
- deterministic financial scope v2;
- Financial Evidence Registry v1/type meanings;
- Financial Evidence decision v1/four dispositions;
- deterministic materializer;
- financial context v1;
- successor prompt v2;
- provider response schema;
- successor artifact family v1;
- legacy immutable artifacts;
- production routing/stage.

Prompt identity remains:

- ref:
  `code:broker_reports_gate2_financial_evidence_successor_prompt_v2`;
- SHA-256:
  `1362c50190bc7859d74b300e5e1fad037cf7ad4939f9946f3c43e4b88930e5fc`.

## Verification

- direct Goal 9A tests: `9 passed in 0.64s`;
- focused successor/context/bundle tests: `55 passed in 3.43s`;
- full Broker Reports suite:
  `1488 passed, 20 skipped, 5 warnings in 105.29s`;
- Ruff on changed maintainable Python: passed;
- three generated bundles rebuilt deterministically;
- provider calls: `0`;
- customer calls: `0`;
- fallback/repair: `0/0`;
- stage mutations: `0`.

The five full-suite warnings are unchanged SWIG deprecation warnings.

## Repository boundary

- base:
  `f507129908088f1c9840d2ed95f2190e12e33561`;
- branch:
  `codex/broker-reports-gate2-ambiguity-goal9a-context-v2`;
- PR: pending creation;
- production admission: false.

## Acceptance

- `ONLY_AUDIT_APPROVED_CHANGES: YES`
- `CONTRACT_IDENTITIES: VERSIONED`
- `REGISTRY_ID_SEMANTIC_DRIFT: ZERO`
- `SYSTEM_METADATA_REINTRODUCTION: ZERO`

Следующий разрешённый шаг только после merge Goal 9A PR:
Goal 9B prompt/provider projection v3 from the new `origin/main`.
