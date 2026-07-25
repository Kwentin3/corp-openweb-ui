# Broker Reports — Gate 2 ambiguity discipline, Goal 3

Дата: 2026-07-25  
Статус: `ELIGIBILITY_ROOT_CAUSE: LOCALIZED`

## Current eligibility path

`DeterministicFinancialScopeFromGate1Factory` создаёт
`FinancialEvidenceDecisionPackage` без `allowed_type_ids`
(`gate2_deterministic_financial_scopes.py:410`).

`Gate2FinancialEvidenceDecisionContractFactory` поэтому:

1. берёт все active Registry types;
2. фильтрует их только по broad `source_family_id`;
3. не проверяет semantic discriminator evidence.

Оба current types совместимы с одной и той же normalized-table source family,
поэтому оба disputed scopes получают:

- `cash_balance_snapshot_v1`;
- `printed_financial_metric_v1`.

После этого `_typed_variant_schema`
(`gate2_financial_evidence_decision.py:452`) проверяет только наличие
value-type/role-compatible refs.

В deterministic scope:

- decimal всегда получает role `amount`;
- date — `as_of_date`;
- currency — `currency`;
- любой text — `source_label`;
- statement-scope ref синтезируется для каждого scope;
- printed-label ref также синтезируется для каждого scope.

Поэтому generic amount/date row становится structurally representable как
cash, даже если source не утверждает cash semantics.

## Per-type eligibility anatomy

### cash_balance_snapshot_v1

Source-family compatibility: passed для обоих disputed cases.

Structural role compatibility:

- amount: present;
- date: present;
- statement scope: always synthesized;
- currency: present.

Missing semantic proof:

- source-stated ordinary cash-class balance;
- unambiguous association amount ↔ cash label;
- exclusion of competing metric hypothesis.

### printed_financial_metric_v1

Source-family compatibility: passed.

Structural role compatibility:

- amount: present;
- statement scope: synthesized;
- printed-label evidence ref: synthesized unconditionally.

Missing semantic proof:

- source-printed total/metric status;
- total/detail row role;
- explicit label association;
- exclusion of calculated/detail value.

Unconditional printed-label ref is identity plumbing, not proof that the source
printed a financial metric.

## Design options

### A — any Registry-compatible type

Rejected. Это current behavior и источник unsafe representability.

### B — typed only when one broad eligible type exists

Safe but недостаточно точен. Current catalog даёт два broad types почти для
каждого normalized table scope, поэтому option B обнулит полезную typed
coverage. Допустим только как conservative fallback.

### C — typed with deterministic discriminator evidence

Accepted target. Code-owned admission policy должен:

- оценить каждый Registry type по machine-readable admission predicates;
- использовать только package-owned Gate 1 evidence;
- требовать positive semantic/structural evidence;
- требовать unique non-conflicting candidate association;
- выдавать admitted type только при доказанном safe match.

Если доказан ровно один type, только он попадает в `allowed_type_ids`.

### D — no typed branch for proven ambiguity

Accepted mandatory guard.

Если:

- admitted types больше одного;
- competing required-role candidates не имеют authoritative association;
- positive discriminator отсутствует;
- source evidence содержит ambiguity/no-safe-signal;

`allowed_type_ids=()`.

Existing canonical schema тогда содержит только:

- `unclassified_financial_input`;
- `no_financial_input`;
- `unsupported`.

Post-response conversion не требуется и запрещён.

## Existing safe integration seam

`FinancialEvidenceDecisionPackage.allowed_type_ids` уже является canonical
pre-model narrowing seam (`gate2_financial_evidence_decision.py:79–83`).

Recommended implementation:

1. новый versioned `TypedAdmissionPolicy` строит value-free admission receipt;
2. successor deterministic scope v2 pin-ит policy identity/evidence hash;
3. factory передаёт admitted IDs через existing `allowed_type_ids`;
4. package-specific strict schema физически исключает unsafe branches;
5. existing parser/validator повторно отвергает type вне eligible IDs;
6. materializer остаётся неизменным.

Receipt должен фиксировать:

- policy/version/hash;
- candidate type IDs;
- admitted type IDs;
- bounded reason codes;
- evidence refs hash/count, не values;
- ambiguity proven;
- exact scope integrity.

Model этот receipt не получает.

## Case outcomes under the rule

- multiple hypotheses:
  competing amount/label associations → ambiguity proven →
  admitted types empty.
- explicit unclassified:
  positive cash/printed discriminator absent and disconfirming source label
  present → admitted types empty.

Оба cases structurally не смогут вернуть typed.

## Acceptance

- `ELIGIBILITY_ROOT_CAUSE: LOCALIZED`
- `SAFE_TYPED_ADMISSION_RULE: OPTION_C_WITH_OPTION_D_FAIL_CLOSED`
- `PRE_MODEL_STRUCTURAL_GUARD: FEASIBLE_USING_EXISTING_ALLOWED_TYPE_IDS`
- `HIDDEN_POST_MODEL_REPAIR: ZERO`

No production/runtime code changed. Provider/customer calls: 0.
Следующий шаг: Goal 4 Registry discriminability audit.
