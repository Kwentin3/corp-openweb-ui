# Broker Reports — Gate 2 ambiguity discipline, Goal 0

Дата: 2026-07-25  
Статус: `FAILURE_EVIDENCE: COMPLETE`

## Результат

Exact evidence chain двух disputed cases заморожена без новых provider calls:

- `syn_successor_multiple_hypotheses`;
- `syn_successor_explicit_unclassified`.

Исходные atomic checkpoints намеренно не содержали raw provider JSON, но
содержали:

- exact model-input hash;
- observed disposition/type;
- canonical materialized-artifact hash;
- provider/schema identity;
- canonical-validation marker.

Audit harness перебрал все допустимые решения соответствующей strict schema,
каждое провёл через существующие
`Gate2FinancialEvidenceValidatedDecisionFactory` и
`Gate2FinancialEvidenceMaterializerFactory`, затем сравнил artifact hash.
Для каждого из четырёх сочетаний «два cases × две attempts» найден ровно один
match. Поэтому exact model decision восстановлен однозначно, а не угадан по
отчёту.

## Attempt difference

Оба cases имели неизменные model-input hashes между attempts.

Attempt 1, prompt v1:

- оба результата: `unclassified_financial_input`;
- все package candidates сохранены;
- binding counts: 8 и 6;
- expected outcome совпал.

Attempt 2, prompt v2:

- оба результата: `typed_input`;
- выбран type `cash_balance_snapshot_v1`;
- binding counts: 5 и 4;
- не все package candidates вошли в typed binding;
- expected outcome не совпал.

Никакие остальные qualification identity fields, кроме двух prompt-derived
fields, между attempts не различались.

## Exact pinned chain

- accepted repository revision:
  `ebf6d94d1c66bbe34a2790c192aa166d3b24f36c`;
- deterministic scope:
  `broker_reports_gate2_deterministic_financial_scope_package_v1`;
- fixture canonical hash:
  `2ad54a8dae7e9e34a4d020310acffad5c76dc049855e5440ed557fb1efe4d687`;
- fixture file SHA-256:
  `b607112e1a70f9877dbd935fdb6f6fe666b61be1ed5b290e896270bde1af886c`;
- Registry:
  `broker_reports_gate2_financial_evidence_registry_v1`,
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`;
- decision contract:
  `broker_reports_gate2_financial_evidence_decision_v1`;
- exact model/provider:
  `gpt-5.4-nano-2026-03-17` / `openai_gpt`;
- provider route revision:
  `4232f7b089fec08326548bf4c70bb33fef0ce603c23d78d6110a9c9a8aec5929`;
- prompt v1 hash:
  `83f22755dd8380b4d91a5b143b1c991afdbed25afea959d9be3d882faee7f33b`;
- prompt v2 hash:
  `1362c50190bc7859d74b300e5e1fad037cf7ad4939f9946f3c43e4b88930e5fc`.

Attempt receipt SHA-256:

- v1:
  `e2f68329f33e50acc3db8e149546041fcf47625074d1587f330932d685277a8f`;
- v2:
  `5332f99a2a3b10bc6d2594fc3aee0c93ce494ba4730eeeac6a9d58303d3b8271`.

Private reconstructed evidence SHA-256:
`af031cc0b45ba1c125b9afd4394abcdd48d9132b6712c56671745eed9b4458ad`.
Private bundle остаётся вне Git.

## Factory and test proof

Canonical reconstruction route:

- `scripts/gate2_successor_ambiguity_audit.py:144`;
- canonical validator invocation: line 160;
- canonical materializer invocation: line 163;
- anti-drift anchors: lines 79–91.

Tests:

- exact four-decision recovery;
- prompt-v1 snapshot hash;
- attempt diff;
- tampered artifact hash fails closed;
- non-prompt identity difference fails closed;
- safe/private separation;
- factory/provider-call anti-drift anchors.

Result: `7 passed in 5.61s`; Ruff: passed.

## Repository boundary

- base:
  `ebf6d94d1c66bbe34a2790c192aa166d3b24f36c`;
- branch:
  `codex/broker-reports-gate2-ambiguity-research-goals0-7`;
- Goal 0 implementation commit:
  `592d413`;
- research PR:
  `https://github.com/Kwentin3/corp-openweb-ui/pull/133`.

Contracts changed: none. Added only research harness/tests and safe evidence.

Explicitly unchanged:

- production/runtime code;
- fixture;
- Registry;
- prompt;
- provider schema;
- validator;
- materializer;
- comparator;
- stage.

## Privacy and effects

- new provider calls: 0;
- customer calls/reads: 0;
- fallback/repair: 0;
- stage mutations: 0;
- source literals/source-value refs in committed receipt: 0;
- raw provider output in Git: 0.

## Acceptance

- `FAILURE_EVIDENCE: COMPLETE`
- `TWO_CASES: EXACTLY_REPRODUCIBLE_FROM_PRIVATE_EVIDENCE`
- `MIXED_REVISIONS: ZERO`
- `NEW_PROVIDER_CALLS: ZERO`

Следующий разрешённый шаг в этом research PR: Goal 1 semantic case anatomy.
