# Broker Reports Direct Role-Value Source Binding v1

Статус: proof-only contract G5.68. Не является product activation.

## Назначение

Metadata-факт публикуется только тогда, когда его value evidence и role evidence имеют собственные точные Canonical addresses и между этими адресами существует прямая уже сохранённая source relation.

Богатый context нужен LLM для понимания. Evidence address нужен validator для доказательства. Composite context не является evidence address.

## Frozen boundary

- metadata contract: `1.0.0`, ровно 11 типов;
- instruction: `1.2.0`, SHA-256 `dd18bcc17c69fd111d29e2bbde4f8aaf6058bfac51b9c9506de25d516ca58d67`;
- context policy: `broker_reports_metadata_context_policy_v4`;
- proposal schema: `broker_reports_llm_metadata_proposal_v2`, SHA-256 `524e8fb2b3b55fb55af3d62fe7465f147f7ad6da18ad9c9cca5b68ecf458ac29`;
- provider/model: `google_gemini` / `models/gemini-3.5-flash`;
- Gate 4, Gate 5 и financial semantics не меняются.

Внутренняя адресная форма имеет версии `broker_reports_llm_metadata_context_v2` и `broker_reports_llm_metadata_binding_registry_v2`. Это structural representation change, не новая semantic policy.

## Exact evidence address

Каждый `m…` alias адресует ровно один непустой Canonical fragment:

- `TEXT`: одна `content.text.lines[n]`;
- `TABLE`: одна `content.cells[n]` с сохранёнными row/column и, только если Canonical действительно хранит header, его header row.

Model-visible region может дополнительно показывать строку и настоящий header. `target_content` и `source_field_path` однозначно отмечают доказательный fragment.

## Допустимые direct relations

Validator знает только структуру:

1. `SAME_ATOMIC_ADDRESS` — role и value ссылаются на одну точную line/cell;
2. `SAME_TABLE_ROW` — две точные cells принадлежат одной row одного node;
3. `TABLE_HEADER_LINEAGE` — role cell является реальным Canonical header той же column, что и value cell.

Same table, same page, source order и близость без одной из этих relations недостаточны.

## Semantic boundary

Validator не знает смысла label, не использует regex, synonyms, blacklist или broker-specific branches. Если модель ссылается на точную локальную label cell и физически связанную value cell, но выбирает неверный fact type, это принимаемая structural связь и чистая semantic ошибка LLM.

## Duplicate boundary

Сохраняется G5.64 contract: одинаковое semantic assertion и value агрегирует несколько evidence locations. Одинаковый literal под разными локальными labels не становится одним source meaning автоматически.

## Execution boundary

Replay допускает ровно один provider submission на документ. Retry, best-of-N, voting, judge, manual repair и повтор после semantic residual запрещены.

## G5.68 proof terminal

```text
DIRECT_ROLE_VALUE_SOURCE_BINDING_PROVEN
COMPOSITE_ROLE_EVIDENCE_OVERREACH_REMOVED
PHYSICAL_AND_ROLE_EVIDENCE_BINDING_VALID
CLIENT_CODE_ACCOUNT_SEMANTIC_ERROR_PERSISTS
PURE_LLM_SEMANTIC_FAILURE_PROVEN
NON_DIRECT_MODEL_EVIDENCE_REJECTED
NO_HEURISTIC_FALLBACK_ADDED
FINANCIAL_GENERALIZATION_PRESERVED
```

General metadata semantic reliability не объявлена: clean replay сохранил дополнительные model residuals. Instruction `1.3.0` и следующий semantic Goal не начинались.
