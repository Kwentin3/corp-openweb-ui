# Broker Reports — Gate 2 Goal 7: full-scope shadow qualification

Дата: 2026-07-24

Статус: `COMPLETED`

## Итог

Registry-driven Gate 2 path квалифицирован shadow-only на полном доступном
авторизованном контуре без browser limits.

Новый path не включался в production и ничего не записывал в stage
ArtifactStore.

## Полный scope

- source-ready documents: `1`;
- parent source units: `12`;
- derived segments: `210`;
- domain packages: `41`;
- canonical decision scopes: `39`;
- authorized selected source refs: `455`;
- strict-schema provider calls: `39`.

Две пары domain packages являлись разными domain-представлениями одного
source ref. Code-owned canonical scope resolution объединил их до provider
decision. Поэтому все 41 packages учтены, но interpretation-bearing scopes
ровно 39 и двойной интерпретации нет.

## Terminal coverage

Rollback baseline:

- selected refs: `455`;
- accounted refs: `448`;
- uncovered refs: `7`;
- rejected packages: `6`.

Registry-driven shadow:

- accounted refs: `455`;
- uncovered refs: `0`;
- excess refs: `0`;
- `unclassified_financial_input`: `32` scopes;
- `no_financial_input`: `7` scopes;
- `typed_input`: `0`;
- `unsupported`: `0`.

Из 410 rollback no-financial refs:

- `393` остались compatibility no-financial terminals;
- `17` были явно замещены Registry-driven interpretation scopes;
- одновременно два противоречащих terminal state для одного ref не
  публиковались.

## Value preservation

В 32 unclassified scopes:

- candidate values: `147`;
- bound values: `147`;
- retention: `100%`;
- fully retained scopes: `32/32`.

Из них `83` — authoritative upstream source values, остальные `64` —
code-owned scope/evidence reference candidates, необходимые для bounded
decision contract.

Literal values, source refs и lineage сохранены в private materialized
artifacts. Customer values и provider raw output в Git отсутствуют.

## Quality gates

- uncovered source refs: `0`;
- unexplained rejected scopes: `0`;
- ownership conflicts: `0`;
- duplicate interpretation facts: `0`;
- contradictory decisions: `0`;
- provider failures: `0`;
- schema failures: `0`;
- fallback: `0`;
- hidden repair: `0`;
- coverage regression: `0`;
- customer values in Git: `0`.

Context projection повторно построена factory-managed кодом для всех 39
canonical scopes. Каждый scope имеет ровно одно interpretation-bearing
представление; остальные representation identities остаются
provenance-only.

## Qualification history

Неуспешные attempts не объединялись с успешным:

1. launcher path error — provider calls `0`;
2. live OpenAI schema rejection из-за `uniqueItems` — сохранён как failed,
   исправлен отдельным PR #87 и подтверждён live synthetic probe;
3. все 39 decisions завершились, но post-processing не сохранил evidence
   из-за nullable baseline metric — attempt не принят;
4. corrected run с per-scope private checkpoint — `PASSED`.

Внутри принятого attempt retry, fallback и repair отсутствуют.

## Explicit catalog limitation

Typed inputs: `0`.

Это не считается failure: initial Registry намеренно содержит только два
узких active type, а полный customer scope не дал достаточного набора
явных date/period и currency/unit bindings для безопасной typed
materialization. Код не подставлял отсутствующие измерения и не создавал
fake typed facts.

Финансовые значения остаются доступными Gate 3 как source-bound
`unclassified_financial_input`. До расширения Registry запрещено утверждать
для них canonical cash/printed-metric type, выполнять tax/accounting
квалификацию или делать выводы, требующие отсутствующих dimensions.

## Evidence

Repository-safe receipt:
[receipt](./BROKER_REPORTS_GATE2_GOAL7_FULL_SCOPE_SHADOW_QUALIFICATION.receipt.safe.json).

Private evidence остаётся только в ignored local contour:

- final private evidence SHA-256:
  `b9031924d497b2b2ad12015019562537a1aaee2081be402ce4e7c034b1ad2c9a`;
- per-scope checkpoint SHA-256:
  `47e07a718645ff165519da08b9a73bbac65f0f908b4d641e194a2f3efa4c2d81`;
- safe receipt source SHA-256:
  `c45d54de448d22c05a61943344f1ea52f560397693c630da6d5214c654c218ff`.

## Validation

- Goal 7 synthetic tests: `7 passed`;
- targeted Gate 2 chain: `91 passed`;
- full Broker Reports suite: `1255 passed`, `20 skipped`;
- ruff: `passed`;
- `git diff --check`: `passed`.

## Acceptance

`AUTHORIZED_SCOPE: COMPLETE`

`TERMINAL_DISPOSITION: ALL_SOURCE_SCOPES`

`UNCOVERED_REFS: ZERO`

`UNCLASSIFIED_VALUE_RETENTION: 100_PERCENT`

`CONTRADICTORY_DECISIONS: ZERO`

`COVERAGE_REGRESSION: ZERO`

`GOAL_7_SHADOW_QUALIFICATION: COMPLETED`
