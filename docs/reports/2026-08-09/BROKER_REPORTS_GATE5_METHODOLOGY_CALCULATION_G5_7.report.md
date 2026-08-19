# Broker Reports Gate 5 — Methodology to Deterministic Calculation (G5.7)

Date: 2026-08-09

Goal status: `G5.7_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

## Verdict

Да. Для текущего Gate 5 существует минимальная практичная машинная граница:

```text
methodology requirements + rule_id + behavior_id + input bindings
-> existing G5.5 satisfied/source-tagged values
-> one reviewed Decimal behavior
-> hash/rule/provenance-bound structured result
```

Rules DSL, runtime code generation и универсальный Tax Engine для этого proof
не нужны.

Результат G5.7 — экспериментальный securities-disposal net result. Это не
утверждение полной налоговой базы РФ и не расчет tax payable.

## Research boundary

Изучены:

- [G5.1 Tax Methodology research](../2026-08-08/BROKER_REPORTS_GATE5_TAX_METHODOLOGY_BOUNDARY_G5_1.report.md);
- G5.2–G5.6 versioned contracts и implementation owners;
- current [Architecture Authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md);
- фактический G5.5 result для Financial Case и Supplemental Fact;
- existing factory, hash-binding и fail-closed repository patterns.

G5.1 уже опирается на актуальные на 2026-08-09 официальные источники и
разделяет tax meaning, deterministic arithmetic и reference data. G5.7 не
добавляет новое юридическое утверждение и не повторяет web/legal research.

Обязательный G5.1 report существовал отдельным committed research branch и не
входил в G5.2–G5.6 stack. Его единственный docs-only commit перенесён в текущую
ветку как prerequisite evidence; runtime Gate 1–4 этим не затронут.

## Что должно меняться вместе с Tax Methodology

Для одного доказанного сценария достаточно:

- `methodology_id` и `methodology_version`;
- stable `rule_id`;
- `behavior_id` известной deterministic implementation;
- G5.4/G5.5 requirements;
- явные bindings requirement values к semantic inputs behavior.

Не доказана необходимость хранить в methodology формулу, Python, expression
tree, произвольные параметры, rate table или reference snapshot.

Applicability по tax period/residency и publication lifecycle нужны полной
Tax Methodology по выводам G5.1, но G5.7 не притворяется, что уже доказал их
runtime selection.

## Что осталось ordinary code

Один маленький runtime владеет только:

- closed-object validation;
- вызовом G5.5;
- требованием `satisfied` для всех inputs;
- извлечением ровно одного scalar value;
- проверкой subject/currency/money;
- `Decimal` addition/subtraction;
- закрытым result projection и canonical projection hash.

Он не выбирает Financial Case types/roles/subject refs и не содержит
representative requirement IDs или значений.

## Рассмотренные варианты

| Вариант | Решение | Причина |
| --- | --- | --- |
| executable formula/DSL внутри methodology | отклонён | один пример не оправдывает parser, execution semantics, safety и отдельное versioning |
| один implicit calculator в orchestration | отклонён | applied behavior скрыт в control flow; methodology частично декоративна |
| methodology ссылается на reviewed behavior | выбран | минимальный явный contract, простой audit/replay, unknown behavior fail-closed |

Реализован один behavior, а не registry/plugin system.

## Representative proof

Tax Methodology projection потребовала:

```text
proceeds amount
proceeds currency
acquisition cost
transaction expense
```

Existing contour вернул:

```text
Financial Case:
  proceeds = 100.00 RUB

Supplemental Facts:
  acquisition_cost = 70.00 RUB
  transaction_expense = 2.00 RUB
```

Все четыре G5.5 requirements получили `satisfied`. Caller не передавал
supplemental artifact refs.

Methodology назвала:

```text
rule_id = experimental-security-disposal-net-result-v0
behavior_id = security_disposal_net_result_v0
```

Deterministic code выполнил:

```text
recognized_expense = 70.00 + 2.00 = 72.00 RUB
net_result = 100.00 - 72.00 = 28.00 RUB
```

Structured output:

```json
{
  "schema_version": "broker_reports_gate5_calculation_result_v0",
  "status": "calculated",
  "outputs": {
    "proceeds": {"kind": "money", "amount": "100.00", "currency": "RUB"},
    "recognized_expense": {"kind": "money", "amount": "72.00", "currency": "RUB"},
    "net_result": {"kind": "money", "amount": "28.00", "currency": "RUB"}
  }
}
```

Полный result также содержит:

- methodology id/version и SHA-256 exact projection;
- calculation/rule/behavior identity;
- все три normalized input values;
- requirement refs;
- Gate 4 `fact_id` для proceeds amount/currency;
- Supplemental Fact refs, scope binding и provenance для расходов.

Новый ArtifactStore/runtime с теми же inputs и projection вернул полностью
идентичный result. Gate 4 до/после структурно равен; calculation runtime не
создал artifacts.

## Financial money surface finding

G5.5 Financial Case source возвращает `amount` и `currency` как отдельные role
requirements. Supplemental money уже возвращается typed object.

Поэтому минимальный calculation binding явно содержит
`amount_requirement_id + currency_requirement_id`. Для supplemental input оба
refs могут указывать на один requirement. Это небольшая contract friction, но
не infrastructure gap и не основание менять G5.5 или создавать unified store.

## Fail-closed proof

Доказано:

- `unknown-behavior-v1` возвращает
  `gate5_calculation_behavior_unsupported`;
- отсутствующий `transaction_expense` возвращает
  `gate5_calculation_inputs_not_satisfied`;
- ни один случай не создаёт result или Supplemental Fact;
- mixed currency, malformed money, cross-subject bindings, несколько
  Financial Case matches и неверный behavior input set также закрыты
  контрактными ошибками;
- fallback, retry, repair, LLM и float arithmetic отсутствуют.

## Tax hardcode

Tax-domain hardcode существует в одном контролируемом месте:

```text
behavior_id
+ exact semantic input interface
+ reviewed arithmetic implementation
```

Methodology-owned hardcode:

```text
какие requirements являются proceeds/acquisition_cost/transaction_expense
+ какой rule/behavior выбран
```

Code-owned hardcode:

```text
recognized_expense = acquisition_cost + transaction_expense
net_result = proceeds - recognized_expense
```

Это допустимая KISS-стоимость. При одном доказанном behavior обычное code
review/versioning проще и безопаснее generic DSL. Если новая методика меняет
только источники/bindings/version и сохраняет behavior, code не меняется. Если
нужна другая арифметика, добавляется новый reviewed behavior и новый ID;
неизвестный ID не исполняется.

## Architecture finding

```text
[ Tax Methodology projection ]
  owns requirements, rule_id, behavior_id, input bindings, version
             |
             | closed machine contract + exact SHA-256 binding
             v
[ Gate5MethodologyCalculationRuntimeFactory.create ]
  reuses G5.5; validates scalar money; executes one Decimal behavior
             |
             v
[ broker_reports_gate5_calculation_result_v0 ]
  methodology/rule/behavior + inputs + source provenance + outputs
```

Tax Methodology владеет изменяемым налоговым выбором. Deterministic code
владеет скучным исполнением известного behavior. Gate 4, G5.3 и G5.5 сохраняют
прежних владельцев.

Отвергнуты executable methodology, implicit calculator и универсальный
framework.

Реально обнаруженная следующая неопределённость: кто и как публикует trusted
immutable methodology и выбирает её по Tax Context/tax period/effective date.
G5.7 доказывает projection/hash seam, но не methodology lifecycle. Этот
вопрос не решался внутри текущего GOAL.

## KISS review

Добавлены:

- один read-only factory-backed runtime;
- один experimental methodology/result contract;
- одна deterministic behavior implementation;
- три focused behavior/anti-drift tests;
- authority/CI routing и этот report.

Не добавлены Tax Engine, DSL, expression interpreter, code generator, plugin
system, Tax Case, Repository, DB/table, workflow, relation engine, graph, LLM,
rates, tax payable, declaration DTO или methodology lifecycle.

## Verification

```text
Focused G5.7: 3 passed
G5.2-G5.7 contour: 18 passed
Extended bundles/ArtifactStore/lifecycle/architecture/Gate 4/G5.2-G5.7/privacy: 138 passed
Managed generator checks: 10 passed
Generated OpenWebUI bundles: byte-stable, no G5.7 product activation
```

## Evidence files

- [G5.7 contract](../../stage2/contracts/BROKER_REPORTS_GATE5_METHODOLOGY_CALCULATION.v0.md)
- [G5.7 runtime](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_methodology_calculation.py)
- [G5.7 tests](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_methodology_calculation.py)
- [Architecture authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md)

## Stop condition

`G5.7_CLOSED`, result `PROVEN`, product status `INACTIVE`.

Следующий Gate 5 slice не начат и не авторизован.
