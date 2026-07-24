# Broker Reports — Economy Goal 2: token, call and cost budget enforcement

Дата: 2026-07-24

Терминальный статус: `COMPLETED`.

## Результат

Добавлен factory-backed budget boundary
`Gate2EconomyBudgetSessionFactory`. Он подключается внутри
`Gate2StructuredModelClientFactory` флагом
`economy_budget_enforcement` и выполняет fail-closed preflight до
provider call.

Goal 2 не меняет production valves, active model и stage bundle. Включение
economy policy в runtime относится к Goal 4, а выпуск — к Goal 7.

Policy обновлена до `1.1.0`; hash:
`0d3e47771fae00178b2fd218319c1c2755bf434a83b6f678cc996cd342ebffd5`.

## Измеренные budgets

| Workload | Input cap | Output cap | Default/fallback calls per operation | Full-scope calls | Per-operation cost cap, USD | Full-scope cost cap, USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gate2_source` | 12 000 | 4 096 | 1 / 1 | 64 | 0.064960 | 2.078720 |
| `gate2_domain` | 12 000 | 4 096 | 1 / 1 | 64 | 0.064960 | 2.078720 |
| `gate2_financial_evidence` | 3 072 | 640 | 1 / 1 | 64 | 0.012544 | 0.401408 |
| `gate2_financial_checksum` | 130 000 | 1 024 | 1 / 0 | 1 | 0.135120 | 0.135120 |

Source/domain сохраняют существующий actual-corpus input bound `12 000`.
Financial evidence caps получены из измеренных максимумов `2 666` input и
`506` output tokens. Checksum caps получены из измерения `117 555` input и
`783` output tokens.

Cost ceilings рассчитаны по token/call caps и самой дорогой разрешённой
economy цене — Haiku. Это fail-closed верхняя граница, а не ожидаемая цена
cheapest-qualified run.

## Pre-call enforcement

Перед вызовом boundary:

- резолвит alias в exact policy model ID;
- отклоняет неизвестный/non-economy model;
- проверяет provider/model binding;
- оценивает input по versioned estimator
  `compact_request_utf8_bytes_div_4_plus_64_v1`;
- устанавливает workload-specific `max_tokens`;
- для minimal reasoning устанавливает `reasoning_effort=minimal`;
- для disabled reasoning удаляет reasoning controls;
- отклоняет tools, functions, plugins и web search;
- проверяет default, fallback и full-scope call counts;
- проверяет estimated operation/full-scope cost;
- при превышении не авторизует provider call.

Anthropic native projection больше не задаёт постоянный
`max_tokens=32768`: она принимает уже проверенный workload cap.

## Post-call accounting

Provider metadata дополнена:

- `cached_input_tokens`;
- `reasoning_tokens`.

Успешный economy call обязан вернуть input/output usage. Boundary повторно
проверяет actual input/output, cached/reasoning accounting, provider и exact
resolved model. Safe receipt содержит только идентификаторы policy/provider/
model, агрегированные tokens/calls/costs, budget status и hashes. Customer
content и provider raw output в receipt отсутствуют.

## Full-scope preflight

На измеренном 39-call financial плане:

- input tokens total: `47 533`;
- fallback calls: `0`;
- conservative output reservation: `39 × 640`;
- Gemini 3.1 Flash-Lite estimated pre-run cost: `$0.049323250`;
- budget status: `within_budget`.

На измеренном checksum input `117 555`:

- planned calls: `1`;
- fallback: `0`;
- Haiku conservative estimate с output reservation `1 024`:
  `$0.122675000`;
- budget status: `within_budget`.

## Verification

- full service suite: `1316 passed, 20 skipped`;
- focused economy/model/runtime/bundle suite: `82 passed`;
- architecture + privacy suite: `23 passed`;
- Ruff для изменённых production/new test files: `passed`;
- compile check: `passed`;
- isolated next-domain-bundle build/import: `passed`;
- provider calls: `0`;
- current live bundles regenerated: `no`;
- stage changed: `no`;
- Gate 1 / Registry / decision / materializer / context change: `0`;
- Knowledge/RAG/vector delta: `0`.

## Acceptance

- `TOKEN_BUDGETS`: `ENFORCED`;
- `CALL_BUDGETS`: `ENFORCED`;
- `REASONING_BUDGET`: `MINIMAL_OR_DISABLED`;
- `PAID_TOOLS`: `ZERO`;
- `COST_ESTIMATE_BEFORE_FULL_RUN`: `PRESENT`;
- `CUSTOMER_CONTENT_IN_SAFE_RECEIPT`: `ZERO`;
- production economy selection: `DEFERRED_TO_GOAL_4`;
- live release: `NOT_PERFORMED`.
