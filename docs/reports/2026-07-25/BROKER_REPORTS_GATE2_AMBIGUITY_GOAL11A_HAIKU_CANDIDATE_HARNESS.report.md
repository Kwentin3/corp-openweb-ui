# Broker Reports — Gate 2 ambiguity discipline, Goal 11A

Дата: 2026-07-25

Статус: `COMPLETED`

## Outcome

После terminal rejection Nano выбран один следующий дешёвый candidate:

`claude-haiku-4-5-20251001`

Выбор ограничен существующей code-owned economy matrix:

- exact model уже зарегистрирована как economy candidate;
- provider profile `anthropic_claude` approved;
- native strict JSON Schema adapter существует;
- модель опубликована по зафиксированному policy evidence;
- reasoning disabled, paid tools/fallback/repair запрещены.

Qualification harness v2 теперь принимает Nano и Haiku через явное
exact-model → provider-profile отображение. Nano остаётся default, его
terminal receipt не изменяется и не переигрывается.

## Почему не Gemini 2.5

Опубликованный `models/gemini-2.5-flash-lite` не совпадает с code-owned exact
Gemini identities `models/gemini-3.1-flash-lite` /
`models/gemini-3.5-flash-lite`.

Добавление 2.5 потребовало бы отдельного изменения policy/provider identity.
В этом Goal матрица не расширяется и новый поиск моделей не начинается.
Gemini 2.5 не объявляется непригодным — он просто вне exact candidate boundary.

## Local preflight proof

Для Haiku на неизменном benchmark v2:

- cases dry-built: `12/12`;
- local Q0/Q1: passed;
- frozen cases: unchanged;
- prompt/input/source-context/provider-projection: unchanged;
- fake exact execution: `12/12`;
- all four dispositions: passed;
- product invariants: passed;
- provider calls: `0`.

Economy estimate:

- estimated input tokens: `21,387`;
- estimated maximum cost: `$0.059787000`;
- maximum output tokens per case: `640`;
- explicit Anthropic structural schema transforms: `24`.

Exact Haiku provider identities:

- profile: `anthropic_claude`;
- adapter: `anthropic_native_messages:1.2.0`;
- provider route revision:
  `289bf0618825d53f49ebe2fda1272aa284e5c5b23f072a262f990c80111d74e7`;
- prompt SHA-256:
  `30c823d2c509294d4634eac1a4084da9b95056b260bdd64e41d5a5598937d9ae`.

## Contracts changed

- qualification harness exact candidate allowlist;
- model-to-provider-profile selection in the qualification-only path;
- local Haiku dry-build/fake-execution tests.

## Contracts unchanged

- benchmark v2 and all cases;
- deterministic scope v2;
- typed admission v1;
- source context v2;
- model input/prompt/provider projection v3;
- Registry and decision semantics;
- validator/materializer/comparator/artifact family;
- economy model policy;
- production allowlist/routing;
- Nano Goal 11 receipt.

## Verification

- focused qualification/economy/provider tests:
  `80 passed in 8.60s`;
- full Broker Reports suite:
  `1522 passed, 20 skipped, 5 warnings in 113.06s`;
- Ruff: passed;
- provider/customer calls: `0/0`;
- persistence/routing mutations: `0/0`.

The five warnings are unchanged SWIG deprecation warnings.

## Repository boundary

- base:
  `f02c7c05757e603b20c9fbcaabdcd37e90d1cf86`;
- branch:
  `codex/broker-reports-gate2-ambiguity-goal11a-haiku-harness`;
- PR: pending creation;
- production admission: false.

## Acceptance

- `CHEAP_CANDIDATE: EXACT_HAIKU_4_5`
- `LOCAL_PREFLIGHT: PASSED`
- `PROVIDER_CALLS: ZERO`
- `NANO_RERUNS: ZERO`

Следующий шаг только после merge этого PR: отдельная one-attempt live Haiku
qualification с отдельным receipt и PR.
