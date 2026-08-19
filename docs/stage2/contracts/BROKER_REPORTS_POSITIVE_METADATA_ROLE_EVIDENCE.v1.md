# Broker Reports Positive Metadata Role Evidence v1

Статус: proof-only contract G5.67. Не является product activation.

## Назначение

Каждый публикуемый metadata-факт обязан иметь два source-backed основания:

1. `source_target_alias` указывает Canonical target, содержащий точное значение;
2. `role_evidence_target_alias` указывает Canonical target, в котором source явно присваивает этому значению заявленную semantic role.

Один target может выполнять обе функции. Для таблицы role evidence может находиться в header target, а value evidence — в row/cell target. Если положительного доказательства роли нет или оно неоднозначно, факт не публикуется.

## Frozen boundary

- metadata contract: `1.0.0`, ровно 11 типов;
- context policy: `broker_reports_metadata_context_policy_v4`;
- proposal schema: `broker_reports_llm_metadata_proposal_v2`;
- instruction: `1.2.0`;
- provider/model: `google_gemini` / `models/gemini-3.5-flash`;
- Canonical, G5.66 structural binding, Gate 4 и Gate 5 не меняются.

## Value boundary

`source_literal` содержит только source-authored value: без role label, delimiter и окружающего описательного текста. Для statement period дополнительно обязательны обе точные boundary literals.

## Validator boundary

Validator проверяет только:

- существование value/role targets;
- принадлежность одному document и Canonical version;
- наличие literal в value target;
- структурную допустимость bindings и непустые source refs.

Validator не определяет человеческий смысл по regex, словарям, synonym lists или broker-specific ветвлениям. Semantic role остаётся ответственностью единственного LLM metadata adapter.

## Duplicate contract

- одно assertion и одно value образуют один fact с несколькими evidence locations;
- разные values остаются разными facts;
- одинаковый literal в разных semantic roles не создаёт автоматическую semantic identity.

## Fail-closed execution

Один документ — один provider submission. Внутренние retry, best-of-N, voting, second-model judge и manual output repair запрещены. Provider output является proposal, а не Canonical authority.

## G5.67 proof status

Контракт структурно реализован, но общая semantic hypothesis не доказана: frozen development corpus прошёл exact source-truth qualification на 3 из 4 документов. На одном документе модель связала client-code value с account role из соседнего содержания того же composite target. Текущий G5.66 unseen holdout прошёл 5/5 и устранил три известных residual без blacklist.

Terminal:

```text
POSITIVE_ROLE_EVIDENCE_NOT_SUFFICIENT
LLM_METADATA_GENERALIZATION_NOT_PROVEN
NO_HEURISTIC_FALLBACK_ADDED
FINANCIAL_GENERALIZATION_PRESERVED
```

Второй untouched holdout в G5.67 не разрешён, поскольку development corpus не прошёл полностью.
