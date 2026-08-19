# G5.67 — Positive Semantic Role Evidence Proof

Дата проверки: 2026-08-15. Статус: `CLOSED_NEGATIVE`.

## Outcome

```text
POSITIVE_ROLE_EVIDENCE_NOT_SUFFICIENT
LLM_METADATA_GENERALIZATION_NOT_PROVEN
EXACT_SEMANTIC_FAILURE_CLASSES_LOCALIZED
NO_HEURISTIC_FALLBACK_ADDED
FINANCIAL_GENERALIZATION_PRESERVED
```

Общий positive-evidence контракт реализован без blacklist и прошёл текущий G5.66 unseen holdout, но не весь frozen development corpus. Поэтому общая гипотеза не доказана, второй untouched holdout не выбирался и semantic tuning после replay не выполнялся.

## Minimal change

Единственный LLM metadata adapter обновлён:

- instruction `1.1.0` → `1.2.0`;
- proposal `broker_reports_llm_metadata_proposal_v1` → `v2`;
- добавлен один обязательный opaque field `role_evidence_target_alias`;
- value target и role target могут совпадать либо быть разными;
- published `source_binding` содержит отдельный `role_evidence_binding`;
- validator проверяет физическое существование и Canonical identity, но не человеческую семантику.

Context policy v4, G5.66 line/table targeting, metadata field set из 11 типов, Canonical, Gate 4 и Gate 5 не менялись. Bundle-проекции регенерированы из maintained source; параллельный runtime owner не создан.

## Mandatory scenario guards

Поведенческими тестами закрыты:

- explicit account/broker/contract role на одном target;
- header-role + row-value на разных targets;
- value без positive role evidence → no fact;
- неизвестный role alias → fail closed;
- contract value без label;
- multiple accounts, duplicates и одинаковый literal в разных contexts сохраняют прежний контракт.

Production instruction не содержит trading/client blacklist. Validator не получил human-language semantic branches, regex или synonym vocabulary.

## Frozen evidence and replay

До provider execution были заморожены contract/instruction/context/schema и source-truth. Offline qualification сохранила:

- source-truth visibility: `24/24`;
- structural ambiguity: `0`;
- semantic hints: `0`;
- broker-specific rules: `0`.

Первый execution route сделал 4 development submissions и один current-holdout submission. Provider был недоступен: development raw evidence содержит HTTP `400` с `Model not found`; current-holdout route также получил typed provider error, но первоначальная версия нового harness не сохранила его raw payload. Повторов внутри execution не было. Harness после этого исправлен только для fail-closed сериализации ошибок; semantic contract не менялся.

По прямому запросу пользователя выполнен отдельный `r2-user-authorized` на том же freeze. Это не скрыто как retry:

- development calls: `4`, по одному на документ;
- current unseen holdout calls: `1`;
- retries внутри calls: `0`;
- best-of-N: `false`;
- manual repair: `false`;
- source stores unchanged: `true`.

Итого по G5.67: `10` provider submissions, из них `5` первых transport-failed и `5` user-authorized semantic replay. Token accounting доступен только для успешных пяти: input `158860`, output `2656`, provider-reported total `178975`. Cost optimization не выполнялась.

## Source-truth qualification

Frozen development corpus против независимого G5.62 visual + Canonical oracle:

| Case | Oracle | Published | Exact | Missing | Extra |
|---|---:|---:|---|---:|---:|
| `pdf_002` | 9 | 9 | yes | 0 | 0 |
| `pdf_024` | 6 | 6 | yes | 0 | 0 |
| `holdout_a` | 3 | 4 | no | 0 | 1 |
| `holdout_b` | 6 | 6 | yes | 0 | 0 |

Итого: `3/4` documents exact, `24/25` published assertions соответствуют source-truth. Все value/role bindings физически валидны; invented literals и invalid provenance равны `0`.

Точный semantic failure class:

```text
CLIENT_CODE_MISCLASSIFIED_AS_ACCOUNT_IDENTIFIER
```

Модель сослалась на один composite table target, где header описывает тип счёта, а отдельная строка явно маркирует значение как client code. Физическая ссылка существует, но cited source structure не связывает само значение с account role. Это доказывает границу подхода: обязательный role reference улучшает проверяемость, но сам по себе не обеспечивает правильную semantic связь внутри composite target.

## Current G5.66 unseen holdout

Результат: `5/5` exact, missing `0`, extra `0`, role-binding failures `0`.

- trading code не опубликован как account;
- company mention без broker/issuer role не опубликован;
- contract опубликован с чистым identifier value, без label и окружающей даты;
- invented literals `0`;
- invalid provenance `0`.

Три известных G5.66 residual устранены общим positive rule, но frozen-corpus failure не позволяет объявить generalization.

## Financial regression

Factory route: `Gate4FinancialCaseRuntimeFactory.create().rebuild_case(...)`.

- `holdout_a`: `39`, `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`, before/after SHA-256 identical;
- `holdout_b`: `129`, `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`, before/after SHA-256 identical;
- exact frozen equality: `true` для обоих.

## Verification

- focused metadata/qualification suite: `46 passed`;
- architecture/cross-gate/canonical suite: `53 passed`;
- failures: `0`;
- bundle maintained-source parity: green;
- only pre-existing SWIG deprecation warnings observed.

Дополнительный unbounded `pytest -q` был остановлен command timeout через `903 s` без terminal summary; он не засчитан ни как PASS, ни как test failure. Bounded suites выше были повторно выполнены после последнего изменения и являются closeout evidence.

## KISS and scope stop

Добавлены один schema field, один positive rule и один тупой structural validation path. Не добавлены blacklist, broker examples, regex, synonyms, ontology, evidence graph, second judge или новый runtime owner.

Так как development corpus не прошёл полностью:

- второй untouched holdout не выбирался;
- prompt/schema/Python semantic tuning после replay: `0`;
- product activation, commit, push и PR не выполнялись;
- следующий архитектурный вопрос не начат.
