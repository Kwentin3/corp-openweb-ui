# Broker Reports — Gate 2 ambiguity discipline, Goal 8

Дата: 2026-07-25

Статус: `COMPLETED`

## Outcome

Реализован code-owned typed-admission guard до model call.

В deterministic scope v2 typed branch присутствует в package-specific
decision schema только при одном доказанном type discriminator. Если
дискриминатор отсутствует, конфликтует или scope содержит несколько
amount/date/currency hypotheses, `allowed_type_ids` пуст и `typed_input`
структурно отсутствует.

Никакого преобразования `typed_input` в `unclassified_financial_input`
после ответа нет.

## New versioned authorities

- `broker_reports_gate2_financial_typed_admission_v1`;
- `gate2_financial_typed_admission_policy_v1`;
- `broker_reports_gate2_deterministic_financial_scope_package_v2`;
- `broker_reports_gate2_deterministic_financial_scope_batch_v2`;
- `gate2_deterministic_financial_scope_from_gate1_v2`.

Existing scope v1 remains available and unchanged. Successor runner and
product comparator explicitly validate either v1 or v2; they do not silently
rewrite a scope.

## Admission rules

Default is fail closed: no admitted type.

Cash admission requires:

- exactly one amount, date and currency candidate;
- exactly one bounded cash discriminator;
- all required evidence in one authoritative Gate 1 association group.

Printed-metric admission requires:

- exactly one amount, date and currency candidate;
- bounded total/subtotal/summary evidence;
- all required evidence in one authoritative Gate 1 association group.

Conflicting cash and printed signals admit no type. Multiple structural
hypotheses admit no type.

Admission produces a value-free safe identity:

- candidate/admitted type IDs;
- aggregate role/context counts;
- reason codes;
- evidence identity hash;
- policy and integrity hashes;
- provider calls `0`;
- post-response conversion `false`.

## Observable acceptance

- unique cash evidence: only cash typed branch is representable;
- unique printed-total evidence: only printed-metric typed branch is
  representable;
- multiple hypotheses: typed branch absent;
- explicit unclassified case: typed branch absent;
- missing discriminator: typed branch absent;
- adjacent equal/FX hypotheses: typed branch absent;
- conflicting positive evidence: typed branch absent;
- fabricated typed decision when not admitted: canonical contract rejects it;
- tampered admission receipt: validator rejects it;
- deterministic rebuild: exact hashes stable;
- v1 scope still exposes its original two Registry-compatible types.

## Contracts changed

- new typed-admission module and factory;
- new deterministic scope v2 package/batch/policy identities;
- v2 validator and explicit v1/v2 validator dispatcher;
- successor runner and comparator accept the explicit v2 scope identity;
- bundle build includes the new closed-world module.

## Contracts explicitly unchanged

- Gate 1 contracts and source authority;
- Financial Evidence Registry v1 and existing type meanings;
- Financial Evidence decision v1 and four dispositions;
- deterministic materializer;
- financial context v1;
- successor model-input v1;
- successor prompt v2;
- successor artifact family v1;
- immutable legacy artifacts;
- source/domain model authority remains zero;
- production routing and stage.

Artifact identity update is intentionally deferred to the Goal 10 benchmark
slice, before any provider call uses scope v2.

## Verification

- direct Goal 8 tests: `15 passed in 0.69s`;
- focused successor/bundle tests: `46 passed in 3.24s`;
- full Broker Reports suite:
  `1479 passed, 20 skipped, 5 warnings in 103.79s`;
- Ruff on changed maintainable Python: passed;
- bundle rebuild determinism: passed for all three generated bundles;
- provider calls: `0`;
- customer calls: `0`;
- fallback/repair: `0/0`;
- stage mutations: `0`.

The five full-suite warnings are unchanged SWIG deprecation warnings.

## Repository boundary

- base:
  `226cede7e972f974b2d3cc74cc2a94607d6d8116`;
- branch:
  `codex/broker-reports-gate2-ambiguity-goal8-typed-admission`;
- PR:
  `https://github.com/Kwentin3/corp-openweb-ui/pull/134`;
- production admission: false.

## Acceptance

- `UNSAFE_TYPED_BRANCH: UNREPRESENTABLE_WHERE_AMBIGUITY_IS_PROVEN`
- `ADMISSION_POLICY: CODE_OWNED_AND_VERSIONED`
- `POST_RESPONSE_REPAIR: ZERO`

Следующий разрешённый шаг только после merge Goal 8 PR:
Goal 9A bounded source context v2 from the new `origin/main`.
