# Broker Reports — Gate 2 ambiguity discipline, Goal 9B

Дата: 2026-07-25

Статус: `COMPLETED`

## Outcome

Реализованы audit-approved prompt v3 и provider projection v3.

Prompt больше не пытается быть единственной ambiguity guard и не содержит
type-specific или fixture-specific правил. Он прямо сообщает, что code-owned
admission уже ограничил strict schema, но наличие typed branch не обязывает
модель выбрать его. `unclassified_financial_input` определён как нормальный
безопасный outcome для финансовых значений без однозначной типизации.

Provider projection не меняет canonical decision branches. Он только
детерминированно ставит `unclassified_financial_input` первым, затем admitted
typed branch, `no_financial_input` и `unsupported`.

## New exact identities

- `broker_reports_gate2_financial_evidence_successor_prompt_v3`;
- prompt SHA-256:
  `30c823d2c509294d4634eac1a4084da9b95056b260bdd64e41d5a5598937d9ae`;
- `broker_reports_gate2_financial_evidence_successor_model_input_v3`;
- `broker_reports_gate2_financial_evidence_provider_projection_v3`;
- `gate2_financial_evidence_unclassified_first_projection_v3`;
- `broker_reports_gate2_financial_evidence_successor_result_v3`.

Prompt v2 remains byte-identical:

- ref:
  `code:broker_reports_gate2_financial_evidence_successor_prompt_v2`;
- SHA-256:
  `1362c50190bc7859d74b300e5e1fad037cf7ad4939f9946f3c43e4b88930e5fc`.

## Prompt responsibility

Prompt v3:

- explains the four terminal outcomes;
- treats unclassified as normal, not exceptional;
- uses source-group nesting as the only value association;
- distinguishes deterministic binding refs from semantic evidence;
- uses bounded Registry definitions/counterexamples as guidance;
- forbids invention, transformation, repair and system metadata.

Prompt v3 does not:

- admit a type;
- add or widen a schema branch;
- name current Registry type IDs;
- mention equal/adjacent fixture patterns;
- receive expected answers;
- replace canonical validation.

## Provider projection proof

For every scope:

- projected branch hashes equal canonical branch hashes as a multiset;
- outer strict response-format contract is unchanged;
- typed IDs exactly equal `decision_contract.eligible_type_ids`;
- ambiguous scope has no typed variant;
- strict JSON schema remains enabled;
- canonical decision validator remains the execution authority.

Model input v3 adds only Registry-owned bounded counterexamples to the accepted
source-groups input v2. Counterexample drift or over-limit content fails
closed.

## Contracts changed

- prompt v3;
- model-input v3 Registry guidance projection;
- provider response-format projection v3;
- successor result v3 safe identity;
- explicit prompt/model-input version pairing;
- closed-world bundle module order.

## Contracts explicitly unchanged

- Gate 1 contracts;
- typed-admission v1 policy/predicates;
- deterministic financial scope v2;
- source context v2;
- Financial Evidence Registry v1/type meanings;
- Financial Evidence decision v1/four dispositions;
- canonical decision schema semantics;
- canonical validator;
- deterministic materializer;
- financial context v1;
- successor artifact family v1;
- legacy immutable artifacts;
- production routing/stage.

## Verification

- direct Goal 9B tests: `9 passed in 0.73s`;
- focused successor/context/projection/bundle tests:
  `64 passed in 3.61s`;
- full Broker Reports suite:
  `1497 passed, 20 skipped, 5 warnings in 105.88s`;
- Ruff on changed maintainable Python: passed;
- three generated bundles rebuilt deterministically;
- external provider calls: `0`;
- customer calls: `0`;
- fallback/repair: `0/0`;
- stage mutations: `0`.

The five full-suite warnings are unchanged SWIG deprecation warnings.

## Repository boundary

- base:
  `4796145c22ef8d9bacd49f1f3cccf16414e3ae95`;
- branch:
  `codex/broker-reports-gate2-ambiguity-goal9b-prompt-v3`;
- PR: pending creation;
- production admission: false.

## Acceptance

- `ONLY_AUDIT_APPROVED_CHANGES: YES`
- `CONTRACT_IDENTITIES: VERSIONED`
- `REGISTRY_ID_SEMANTIC_DRIFT: ZERO`
- `SAFETY_ONLY_IN_PROMPT: FORBIDDEN`

Следующий разрешённый шаг только после merge Goal 9B PR:
Goal 10 frozen successor benchmark v2 from the new `origin/main`.
