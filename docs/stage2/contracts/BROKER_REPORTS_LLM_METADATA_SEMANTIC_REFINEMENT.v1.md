# Broker Reports LLM Metadata Semantic Refinement v1

Status: `G5_65_NEGATIVE_HOLDOUT_TERMINAL`

## Authority boundary

Этот addendum не создаёт новый metadata owner. Набор и machine meaning 11 полей
остаётся у `BROKER_REPORTS_MINIMAL_PERSON_DOCUMENT_METADATA` `1.0.0`.
Единственный model-visible owner формулировки —
`GATE3_LLM_METADATA_INSTRUCTION` версии `1.1.0`.

Canonical, context packaging v3, source binding, proposal schema, physical and
provenance validation, provider/model route, deterministic G5.60 extractor,
financial pipeline, Gate 4 и Gate 5 frozen.

## Minimal semantic refinement

Разрешённый смысловой delta ограничен четырьмя границами:

- `ACCOUNT_IDENTIFIER` означает явно обозначенный брокерский или
  инвестиционный счёт; идентификатор клиента или стороны не становится счётом
  только из-за идентификации клиента;
- `ACCOUNT_CONTRACT_IDENTIFIER` сохраняет полное source-authored обозначение
  договора или соглашения как одну представленную source единицу, без
  произвольного обрезания и без присоединения соседних отдельных metadata;
- `DOCUMENT_TYPE` содержит только source-authored название вида текущего
  документа, а не весь смешанный заголовок с соседними metadata;
- `PERSON_CITIZENSHIP` требует явного утверждения гражданства лица;
  identity-document, issue, registration, residence и tax-residency assertions
  сами по себе такого утверждения не создают.

Остальные определения не менялись: существующие границы report/account subject,
document date/number, issuer, period и missing/ambiguous evidence достаточны.

Broker-specific examples, few-shot content, synonym vocabulary, human-language
regex, per-document prompts и Python semantic branches: `0`.

## Execution law and terminal

Frozen replay разрешён ровно один раз для четырёх документов, по одному
submission на документ, без retry, best-of-N и repair. Если Phase 1 не даёт
приемлемого semantic result, unseen holdout не выбирается и не исполняется.

Первый G5.65 replay не дошёл до model output: все четыре submissions получили
provider boundary `400 Model not found`. После прямого разрешения пользователя
второй replay в отдельном output root получил `24/24` exact against G5.62.

Обязательный unseen holdout затем завершился strict rejection из-за ambiguous
literal binding и показал semantic extras: trading code как account, неявную
broker role и label overinclusion в contract identifier. Contract после
holdout не менялся. Addendum остаётся proof-only и не активирует LLM adapter в
product.

```text
LLM_METADATA_SEMANTIC_GENERALIZATION_NOT_PROVEN
EXACT_SEMANTIC_FAILURE_CLASSES_LOCALIZED
NO_RUNTIME_HEURISTIC_FALLBACK_ADDED
```
