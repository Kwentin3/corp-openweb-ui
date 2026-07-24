# Broker Reports — Gate 2 Goal 0: operational containment

Дата: 2026-07-24

Статус: `COMPLETED`

## Итог

Регрессивный semantic-selection release локализован. Stage атомарно переведён
с `broker-reports-97c703405017` на принятую `main` revision
`530dd29b820aa9e82e1199796fab46c7d04e691c`.

Перед изменением independent read-only verifier подтвердил:

- live release и обе Gate 2 Function identities точно соответствовали
  регрессивному release;
- `semantic_selection_enabled` был `true`;
- rollback identity был точен;
- workload был quiescent;
- release staging был пуст.

После merge PR #78 atomic release изменил ровно две Gate 2 Functions. Gate 1,
Action, loader, 12 managed prompts, image и private-intake contract остались
без изменения.

## Containment

`broker_reports_gate2_domain_source_fact_pipe` восстановлен byte-for-byte до
последней pre-release baseline identity:

`c26ae568bcaa8987abb581528abe20299ff50d3b853d402d31253211349be6dd`.

`broker_reports_gate2_source_fact_pipe` восстановлен к baseline runtime и
получил один дополнительный fail-closed guard:

- release valve всегда устанавливает `semantic_selection_enabled=false`;
- production Pipe не читает `semantic_selection_enabled` из workload config;
- попытка operator valve установить `true` не включает runtime path;
- повторное включение возможно только новой code-owned migration после
  qualification.

Новая source Function identity:

`d3ba38ed554d87e01a97d7dceaffee71eaa02c88375706477d819f4ccc83d503`.

## Atomic proof

- release ID: `broker-reports-530dd29b820a`;
- manifest SHA-256:
  `a32769d18aaf1f60e5638ac4741d4c59bffb4aa5a8dde4ab74613085b14fc982`;
- rollback identity SHA-256:
  `8e36a1c5d5c1fa4b8f28d6722da2489dd3eb468bd61c755832af62f304e724c2`;
- previous state restored: `true`;
- candidate state reapplied: `true`;
- loader restored on both rehearsal legs: `true`;
- independent read-only verifier: `passed`;
- repository/live parity: `exact`.

## Invariants

| Invariant | Result |
|---|---|
| Gate 1 Function delta | `ZERO` |
| Action delta | `ZERO` |
| loader delta | `ZERO` |
| managed prompt delta | `ZERO` |
| image delta | `ZERO` |
| Knowledge rows delta | `ZERO` |
| Document rows delta | `ZERO` |
| File rows delta | `ZERO` |
| vector files/bytes delta | `ZERO` |
| nonterminal workload jobs | `ZERO` |
| owned temp entries | `ZERO` |
| release staging entries | `ZERO` |

Локальная проверка exact delivery tree:

- targeted Gate 2/release tests: `69 passed`;
- full Broker Reports suite: `1147 passed`, `20 skipped`;
- repository privacy guard входит в полный suite и прошёл.

## Ограничение

Rollback не закрывает Gate 2. Baseline ранее имел `35/41` accepted packages и
`7` uncovered refs. Goal 0 только убирает доказанно более регрессивное
состояние `21/41` и `42` uncovered refs. Новый Registry-driven path должен
пройти отдельную full-scope shadow qualification до production migration.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GATE2_GOAL0_OPERATIONAL_CONTAINMENT.receipt.safe.json).

## Acceptance

`LIVE_IDENTITY: READ_ONLY_VERIFIED`

`REGRESSIVE_SEMANTIC_SELECTION: ROLLED_BACK`

`SEMANTIC_SELECTION_DEFAULT: DISABLED`

`WORKLOAD_CONFIG_REENABLE: FORBIDDEN`

`GATE1_RUNTIME_CHANGE: ZERO`

`KNOWLEDGE_RAG_VECTOR_DELTA: ZERO`

`ROLLBACK_PROOF: PASSED`

`GOAL_0_OPERATIONAL_CONTAINMENT: COMPLETED`
