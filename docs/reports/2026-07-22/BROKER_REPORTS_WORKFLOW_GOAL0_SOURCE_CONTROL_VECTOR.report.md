# Broker Reports — Goal 0: source-only control vector

Дата: 2026-07-22

Статус: `COMPLETED`

## Результат

До запуска пользовательского workflow выбран и запечатан приватный semantic-checksum vector для одного ранее авторизованного broker-report PDF. Вектор содержит ровно три материальные метрики из трёх разных логических source scopes. Все три относятся к raster/semantic visual-table route; для одной метрики применима и успешно проверена однозначная арифметическая сверка.

Ожидаемые названия, суммы, страницы и приватные ссылки не включены в Git. Они остаются в ignored evidence, недоступном Gate 1, Gate 2, context assembler, answering LLM, VLM providers и managed prompts.

## Source-only процедура

- Исходный PDF открыт и проверен непосредственно, а не через provider output.
- Метрики выбраны до начала тестового workflow.
- Reviewer authority: `delegated_agent`.
- `human_reviewed`: false.
- `customer_accepted`: false.
- Provider output как reference truth не использовался.
- Для каждой приватной метрики сформирован отдельный integrity hash; весь reference защищён общим seal.
- Повторная запись в непустой reference directory запрещена контрактом.

## Терминальный gate

| Инвариант | Результат |
|---|---:|
| `CONTROL_VECTOR_METRICS` | `EXACTLY_THREE` |
| `METRICS_SELECTED_BEFORE_WORKFLOW` | `PASSED` |
| `SEMANTIC_VLM_METRIC` | `THREE_OF_THREE` |
| `DISTINCT_LOGICAL_SOURCE_SCOPES` | `THREE` |
| `ARITHMETIC_RECONCILIATION` | `ONE_APPLICABLE_ONE_PASSED` |
| `SOURCE_ONLY_REFERENCE` | `SEALED` |
| `PROVIDER_OUTPUT_USED_AS_REFERENCE` | `ZERO` |
| `EXPECTED_VALUES_EXPOSED_TO_RUNTIME` | `ZERO` |
| `DELEGATED_REVIEW_AUTHORITY` | `EXPLICIT` |
| `PRIVATE_REFERENCE_COMMITTED_TO_GIT` | `ZERO` |

## Проверки

- Целевой contract suite: `9 passed`.
- Затронутая регрессия вместе с actual-corpus reference и repository privacy guard: `18 passed`.
- Python static check: `All checks passed`.
- Проверены fail-closed случаи: неверное число метрик, повторный scope, арифметическое расхождение, provider-derived truth, неверный reviewer status и попытка перезаписи sealed reference.
- Safe receipt не содержит literal labels, printed values или normalized comparison values.
- Фактический SHA-256 приватного reference совпадает с seal.
- Все приватные reference artifacts подтверждённо покрыты `.gitignore`.

## Безопасные идентичности

- source document SHA-256: `738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57`;
- control vector SHA-256: `ea7ad387abd9380a94020fd0d6837cbda12c1ac03a3dcbe85dda96387b27ac5c`;
- private reference SHA-256: `2cdd51bb4235dadb10634c9853b56c95815bf06b6612676e362606d85a503aab`;
- private reference seal SHA-256: `607000fb3a42ba1cacfd081af29c2b6dbe79ad9d181bfa0a8b4de82a11d6431d`;
- repository safe receipt SHA-256: `5770d805b3b870b22ebced1c2f3b2a818ea1b845a6515b900666297adbe196c8`.

Repository-safe evidence: [safe receipt](./BROKER_REPORTS_WORKFLOW_GOAL0_CONTROL_VECTOR.receipt.safe.json).

## Решение

`GOAL_0_SOURCE_CONTROL_VECTOR: COMPLETED`

Goal 1 может начинаться только после merge этого изолированного Goal 0 branch в актуальный `main`.
