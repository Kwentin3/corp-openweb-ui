# Broker Reports — atomic release domain semantic selection

Дата: 2026-07-23

Ветка: `codex/broker-reports-goal5-domain-semantic-selection-release-v1`

Статус: `PASSED`

## Итог

Исправление model-facing контракта Gate 2 выпущено на stage из точной
принятой ревизии:
`97c70340501725fc7dd2d0e4f5bc0dc977946989`.

- release ID: `broker-reports-97c703405017`;
- manifest SHA-256:
  `72ffeb5c3818b3da9ae106c7251a1c93e2d44652b2f289c93bfd600f66f52e9d`;
- rollback identity SHA-256:
  `a31fa3da4b6ba946d52f951aac438610b90cd7a167d069b8cdd23dcd9ff8b485`;
- atomic apply: passed;
- rollback proof: passed;
- independent verifier: passed.

## Граница выпуска

Изменились ровно две Gate 2 Functions:

| Runtime object | До | После |
|---|---|---|
| `broker_reports_gate2_source_fact_pipe` | `45de78ac87f44a7f30d8dacc4d3d1bd3edbbafbc5002708776726d51edf2ce3e` | `69bef1b4c53d17cc094ab3f19d307c781b3aeb427959463bbac05acfde5a5d9e` |
| `broker_reports_gate2_domain_source_fact_pipe` | `c26ae568bcaa8987abb581528abe20299ff50d3b853d402d31253211349be6dd` | `3f04ae75852e1e676091e01a92fec15a8795e7c97d282b76a5976443b5e42fe3` |

Не изменились:

- Gate 1 Function:
  `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519`;
- private intake Action:
  `874a07129aa626e61807095b19e531972395934ce1a9aad72d378a3104530ae4`;
- loader:
  `51e836b02e2c71aa61e2ff4faff0e43f762b70d3ecf41fdbbffb73bf5d3891f7`;
- все `12` managed prompts;
- image identity и private-intake contract.

Live content обеих Gate 2 Functions в точности совпадает с repository bundles.
Это подтверждает, что domain Pipe использует облегчённый semantic-selection
контракт из принятого кода, а не локальную или частично обновлённую копию.

## Rollback proof

Существующий atomic release tooling выполнил полную последовательность:

1. установил candidate;
2. создал rollback artifact;
3. восстановил прежние Functions и loader;
4. проверил прежние identities;
5. повторно установил candidate;
6. проверил candidate identities;
7. удалил release staging.

Финальное состояние stage — candidate. Предыдущее состояние доказанно
восстановимо.

## Проверки

Перед выпуском на принятом `main`:

- полный Broker Reports suite: `1149 passed`, `20 skipped`;
- repository privacy guard: `3 passed`;
- worktree clean;
- `HEAD == origin/main`;
- commits ahead of `origin/main`: `0`.

После выпуска независимый verifier подтвердил:

- все три Function bundle exact;
- все `12` prompts exact;
- Action, loader, image, manifest и source revision exact;
- factory boundary passed;
- semantic visual-table contract identity exact;
- rollback identity exact;
- workload quiescent;
- owned temp entries: `0`;
- release staging entries: `0`.

## Counter invariants

До и после значения совпали:

| Counter | До | После |
|---|---:|---:|
| Knowledge rows | 0 | 0 |
| Document rows | 0 | 0 |
| File rows | 273 | 273 |
| Vector files | 595 | 595 |
| Vector bytes | 309808908 | 309808908 |

Knowledge/RAG/vector mutation отсутствует.

## Ограничение

Atomic release доказывает repository/live parity и rollback, но не доказывает
финансовое качество нового model-facing контракта на полном клиентском scope.
Следующий обязательный шаг — новый полный Gate 2 run на этой live-ревизии.

## Безопасность

В Git не записаны клиентские названия, суммы, исходное имя файла, raw provider
output, приватные source refs или credentials.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GOAL5_DOMAIN_SEMANTIC_SELECTION_ATOMIC_RELEASE.receipt.safe.json).

## Решение

`ATOMIC_RELEASE: PASSED`

`ROLLBACK_PROOF: PASSED`

`REPOSITORY_LIVE_PARITY: EXACT`

`FULL_GATE2_REPROOF: REQUIRED`
