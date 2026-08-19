# Broker Reports Unseen Holdout Precise Source Binding Contract v1

Статус: `CLOSED_WITH_LOCALIZED_SEMANTIC_RESIDUALS`
Goal: `G5.66`

## Scope

Этот addendum разрешает только structural refinement metadata context package:
каждая непустая естественная `Canonical TEXT` line получает отдельный opaque
target address. Для small tables сохраняется существующий `row + header` target.

Заморожены и не меняются:

- unseen holdout и его visual source-truth oracle из G5.65: `5` facts;
- metadata contract `1.0.0`, 11 fact types;
- instruction `1.1.0` и proposal schema;
- `google_gemini` / `models/gemini-3.5-flash`;
- financial pipeline, Gate 4 и Gate 5.

## Structural law

Packager использует только существующую Canonical structure: document, node,
text line, table row/cell и source order. Oracle не является входом selection.
Semantic selectors, broker/layout branches, fixed character windows, regex,
synonym vocabulary и invented headings запрещены.

Validator принимает proposal только когда literal находится ровно в одном
Canonical fragment выбранного target. Same literal в разных source lines не
схлопывается автоматически; существующая G5.64 evidence aggregation продолжает
опираться на structural source meaning.

## Replay law

Provider разрешён только после offline proof:

- holdout visibility `5/5`;
- holdout physical binding ambiguity `0`;
- frozen G5.62 corpus visibility `24/24`;
- frozen structural ambiguity `0`.

После proof разрешён один holdout submission. Retry, best-of-N, manual repair и
post-output semantic tuning запрещены.

## Closed result

```text
UNSEEN_HOLDOUT_SOURCE_BINDING_PROVEN
REPEATED_LITERAL_PHYSICAL_AMBIGUITY_ZERO
HOLDOUT_ORACLE_VISIBILITY_5_OF_5
FROZEN_METADATA_VISIBILITY_24_OF_24_PRESERVED
SAME_LLM_INSTRUCTION_1_1_REPLAY_COMPLETED
FINANCIAL_GENERALIZATION_PRESERVED
LLM_METADATA_SEMANTIC_RESULT=RESIDUAL_FAILURES_LOCALIZED
```

Остались только три не исправлявшихся semantic residuals:

- `TRADING_CODE_MISCLASSIFIED_AS_ACCOUNT_IDENTIFIER`;
- `BROKER_ROLE_INFERRED_NOT_EXPLICIT`;
- `CONTRACT_IDENTIFIER_LABEL_OVERINCLUSION`.

Product activation и следующий semantic Goal этим addendum не разрешены.
