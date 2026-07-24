# Broker Reports — Economy Goal 4: deterministic provider selection

Дата: 2026-07-24

Терминальный статус: `COMPLETED`.

## Результат

Gate 2 production Pipes подключены к code-owned economy policy через
`Gate2EconomyProviderSelectionFactory`. Выбор выполняется по правилу:

`cheapest_qualified_first_then_preference_order_then_exact_id`.

Стоимость сравнивается детерминированно на верхних input/output token caps
соответствующего workload. `preference_order` и exact ID используются как
фиксированные tie-breaks.

Runtime model/provider config теперь может только сузить qualified allowlist.
Пустой model/provider config выбирает первый допустимый binding. Любая попытка
указать неизвестную, дорогую или неподтверждённую модель завершается до
создания provider client и до provider call.

## Текущий fail-closed результат

Policy `broker_reports_economy_model_policy_v1` версии `1.2.0`, hash
`e6a297c359ff55fe48b22cf568261ae3bc0e329378f648b6438227e9a93ef35c`,
не содержит qualified/active моделей. Поэтому production selection для
`gate2_source`, `gate2_domain` и `gate2_financial_evidence` возвращает typed
blocker:

`gate2_economy_no_qualified_model`.

До этого terminal status:

- provider calls: 0;
- fallback calls: 0;
- expensive tier calls: 0;
- persisted partial success: 0.

## Runtime contract

- основной binding: ровно один;
- параллельный provider consensus: отсутствует;
- fallback candidate: не более одного, только из qualified economy allowlist;
- checksum workload: fallback запрещён policy;
- hidden retry/repair: отсутствует;
- domain и financial workloads получают независимые policy bindings и
  независимые provider admission slots;
- economy token/call budget enforcement включён на source, domain и financial
  production clients;
- safe runtime metadata содержит policy ID/version/hash и exact model/provider.

Qualification mode отделён от production selection. Он допускает только
зарегистрированный economy candidate с совпадающим provider profile; status
`QUALIFIED` для capability probe не требуется, но дорогой/неизвестный ID
отклоняется до вызова.

## Проверки

- selector/policy/budget/bundle/architecture focused suite: `70 passed`;
- full regression suite: `1328 passed, 20 skipped`;
- synthetic qualified-policy test: cheapest-first и фиксированный fallback;
- current policy test: typed no-qualified blocker;
- narrowing tests: runtime не расширяет model/provider allowlist;
- checksum test: fallback maximum равен нулю;
- closed-world bundles содержат selection factory и budget enforcement;
- прямой старый `gate2_resolve_extraction_model_id` удалён из production Pipes.

## Acceptance

- `CHEAPEST_QUALIFIED_FIRST`: `PASSED`;
- `DEFAULT_PROVIDER_CALLS`: `ONE`;
- `MULTI_PROVIDER_CONSENSUS`: `ZERO`;
- `FALLBACK_CALLS_MAXIMUM`: `ONE`;
- `EXPENSIVE_TIER_ESCALATION`: `ZERO`;
- `GOAL_4_PROVIDER_SELECTION`: `COMPLETED`.
