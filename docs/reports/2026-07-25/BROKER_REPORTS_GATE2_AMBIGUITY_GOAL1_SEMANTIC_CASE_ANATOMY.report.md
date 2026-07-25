# Broker Reports — Gate 2 ambiguity discipline, Goal 1

Дата: 2026-07-25  
Статус: `SEMANTIC_CASE_ANATOMY: PASSED`

## Метод

Анализ использовал только замороженный Goal 0 private bundle и repository
contracts. Новых model/provider calls и customer reads не было.

Typed не считался ошибкой только из-за несовпадения с fixture. Для каждого
case отдельно проверены:

- source semantics;
- exact model input;
- available Registry types/roles;
- uniquely recovered provider decision;
- supporting и contradicting evidence;
- downstream product meaning.

## Case: multiple hypotheses

### Source fragment

Один bounded table-row scope содержит:

- две разные tentative financial labels;
- две разные decimal values;
- одну дату;
- одну валюту;
- deterministic statement-scope и printed-label refs.

Всего model-facing source values: 8.

### Что получила модель

- eligible types:
  `cash_balance_snapshot_v1`,
  `printed_financial_metric_v1`;
- обе Registry definitions;
- value type и allowed role каждого source value;
- literal labels/values;
- strict four-disposition schema.

Не были переданы authoritative associations между:

- первой label и первым amount;
- второй label и вторым amount;
- label/amount и semantic hypothesis;
- row/column structural meaning.

Flat `source_values` сохранил literals, но потерял композицию двух гипотез.

### Exact observed choice

Prompt v2 decision однозначно восстановлен:

- disposition: `typed_input`;
- type: `cash_balance_snapshot_v1`;
- использованы один из двух amounts, дата, валюта, statement scope и одна
  tentative cash label;
- competing amount/label и printed-label ref не вошли в typed binding.

Decision SHA-256:
`a1627ab21cb7e729465d2df9784d20028e2eb8ac774ac1e72405a948f79dc014`.

### Semantic assessment

Поддерживает cash:

- один label содержит tentative cash meaning;
- доступны structurally compatible amount/date/currency/scope roles.

Противоречит safe cash admission:

- label является tentative, а не source-stated ordinary cash balance;
- существует конкурентная metric hypothesis;
- имеется второй amount;
- package не доказывает, какой amount относится к какой hypothesis;
- оба Registry types structurally representable;
- выбранный typed binding не покрывает competing financial candidates.

`typed_input` здесь не является семантически приемлемой альтернативой.
Единственный безопасный outcome:
`unclassified_financial_input` с сохранением всех восьми candidates.

Классификация:

- primary: `CONTEXT_INSUFFICIENT`;
- outcome: `EXPECTED_UNCLASSIFIED_UNIQUELY_REQUIRED`;
- contributing: `ELIGIBILITY_TOO_BROAD`;
- contributing: `MODEL_OVER_TYPING`;
- prompt-v2 branch bias: требует отдельного Goal 5 вывода.

Product risk: ложный cash balance в financial context и потеря competing
hypothesis из typed projection, несмотря на сохранность literals в source
package.

## Case: explicit unclassified

### Source fragment

Один bounded row содержит:

- explicit label, обозначающий unmapped financial row;
- одну decimal value;
- одну дату;
- одну валюту;
- deterministic statement-scope и printed-label refs.

Всего model-facing source values: 6.

### Что получила модель

Модель получила literal source label, обе Registry definitions и все
shape-compatible roles. В отличие от первого case, ключевой disconfirming
semantic context в input присутствовал.

### Exact observed choice

Prompt v2 decision однозначно восстановлен:

- disposition: `typed_input`;
- type: `cash_balance_snapshot_v1`;
- использованы amount/date/currency/statement scope;
- `source_label` оставлен `null`;
- balance-class evidence отсутствует.

Decision SHA-256:
`1aa572a997703852f3a332e94e49827a6a0a8625402a93666323482ad4517cce`.

### Semantic assessment

Поддерживает cash только structural shape:

- amount;
- reporting date;
- currency;
- synthesized statement-scope ref.

Противоречит cash:

- source не утверждает ordinary cash balance;
- explicit source label утверждает отсутствие Registry mapping;
- модель не привязала этот label как evidence;
- cash definition требует source-stated cash-class balance;
- presence amount/date/currency не доказывает cash semantics.

`typed_input` не является семантически приемлемой альтернативой.
`no_financial_input` также неверен, поскольку financial literal присутствует.
Единственный безопасный outcome:
`unclassified_financial_input` с сохранением всех шести candidates.

Классификация:

- primary: `ELIGIBILITY_TOO_BROAD`;
- outcome: `EXPECTED_UNCLASSIFIED_UNIQUELY_REQUIRED`;
- contributing: `MODEL_OVER_TYPING`;
- context sufficiency: sufficient for rejection, but not enforced by typed
  admission/schema;
- Registry machine-discriminability: требует Goal 4.

Product risk: generic amount/date row становится canonical cash snapshot без
source-stated cash evidence.

## Cross-case conclusion

Оба failures не имеют одной причины:

| Layer | Multiple hypotheses | Explicit unclassified |
|---|---|---|
| Source literals | Complete | Complete |
| Model context | Association lost | Disconfirming label present |
| Eligible types | Too broad | Too broad |
| Typed schema | Unsafe branch present | Unsafe branch present |
| Model behavior | Picks one hypothesis | Ignores/omits contradicting label |
| Safe outcome | Unclassified only | Unclassified only |

Ни validator, ни materializer не дефектны относительно текущего contract:
они корректно приняли representable typed decisions. Дефект возникает раньше:
unsafe type оказался admissible и representable без доказательства его
semantic condition.

## Acceptance

- `EXPECTED_OUTCOME_UNIQUENESS: PROVEN_PER_CASE`
- `OBSERVED_TYPED_CHOICE: SEMANTICALLY_EXPLAINED`
- `PRODUCT_RISK: EXPLICIT`

Contracts/runtime/stage unchanged. Provider/customer calls: 0.
Следующий шаг: Goal 2 model-input sufficiency audit.
