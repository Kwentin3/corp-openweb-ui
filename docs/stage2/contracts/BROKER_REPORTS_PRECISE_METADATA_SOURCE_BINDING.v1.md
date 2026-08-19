# Broker Reports Precise Metadata Source Binding v1

Status: `PROVEN_IN_G5_64_PROOF_ONLY`

## Boundary

Этот contract уточняет только source addressability и публикацию повторных
подтверждений для неизменного
`BROKER_REPORTS_MINIMAL_PERSON_DOCUMENT_METADATA` `1.0.0`.

Не меняются 11 fact types, их meaning/cardinality, LLM instruction `1.0.0`,
proposal schema `broker_reports_llm_metadata_proposal_v1`, model/provider,
финансовый pipeline, Gate 4 и Gate 5. Product activation и новая persistence не
разрешены.

## Structural packaging

Packaging идёт в Canonical source order и не принимает oracle:

- `TEXT` остаётся реальным Canonical text block; после выбора opaque target
  validator обязан связать `source_literal` ровно с одним конкретным
  `content.text.lines[n]` fragment;
- малая `TABLE` с не более чем 64 непустыми cells публикуется как отдельные
  `SMALL_TABLE_ROW_WITH_HEADER` targets: первая structural row как header плюс
  ровно одна текущая row;
- isolated cells, synthetic headings, semantic selectors, broker wording,
  page/column rules и position cutoffs запрещены;
- таблицы крупнее существующего structural limit не становятся metadata
  targets.

Source unit достаточен только когда выбранный literal соответствует ровно одному
Canonical fragment. Exact field path, node, document/version и source refs
проверяются fail closed.

## Repeated evidence publication

Каждый proposal сначала независимо проходит физическую и value validation.
После этого один publication group возможен только при совпадении:

```text
document + canonical version
+ fact type
+ normalized value
+ structural source-meaning context
```

Structural source-meaning context не является semantic selector:

- для text это реальная Canonical line, содержащая source literal;
- для table это реальный header row context и structural column.

Одна group публикует один normalized source fact. Primary binding — первое
место в детерминированном source order. Все подтверждения сохраняются в
`source_binding.evidence_locations`; primary не объявляется более истинным.

Повтор того же proposal на том же physical binding остаётся ошибкой модели и
fail closed отклоняется.

## Negative law

- один fact type с разными normalized values публикуется как несколько facts;
- несколько account identifiers и statement periods не reconcile и не
  выбираются по приоритету;
- одинаковый literal в разных source contexts не схлопывается автоматически;
- ошибочно названный `PARTY_NAME` для signer не маскируется dedup;
- client code не становится account identifier;
- паспортная формулировка не становится citizenship;
- oracle измеряет результат после packaging и не участвует в selection,
  binding или publication.

## Proof-only status

G5.64 доказал structural binding и duplicate-evidence behavior на frozen corpus
и deterministic mandatory scenarios. Это не меняет действующего metadata owner,
не активирует LLM adapter в product runtime и не разрешает semantic tuning.
