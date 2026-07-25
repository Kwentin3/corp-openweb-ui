# Broker Reports — Gate 2 ambiguity discipline, Goal 6

Дата: 2026-07-25  
Статус: `BENCHMARK_EXPECTATIONS: PRODUCT_GROUNDED`

## Evaluation rule

Benchmark expectation считается корректным не по имени fixture, а если
альтернативный observed outcome меняет product semantics или нарушает central
safe-admission invariant.

Проверены:

- source meaning;
- complete alternatives among four dispositions;
- materialized financial input;
- `broker_reports_gate2_financial_context_v1`;
- future Gate 3 risk;
- literal/ref preservation;
- terminal ownership.

## multiple hypotheses

### Semantic alternatives

`typed_input`:

- cash — небезопасно: существует competing metric hypothesis и нет unique
  amount association;
- printed metric — небезопасно по той же причине;
- любой другой Registry type отсутствует.

`no_financial_input` — неверно: financial values присутствуют.

`unsupported` — неверно: source shape поддерживается.

`unclassified_financial_input` — единственный outcome, который:

- сохраняет обе hypotheses;
- сохраняет все values/refs;
- не создаёт фиктивный canonical type;
- явно сообщает ambiguity.

### Downstream effect of observed typed cash

Financial context получает:

- status `typed_input`;
- cash input type/semantic class;
- только selected typed bindings в interpretation representation.

Competing amount/label остаются в provenance-only representation, но не
являются финансовой interpretation hypothesis. Это не naming difference:
future Gate 3 может использовать ложный cash balance как typed state.

Expected unclassified uniquely required: yes.

## explicit unclassified

### Semantic alternatives

`typed cash` — неверно: source-stated cash evidence отсутствует.

`typed printed metric` — неверно: printed total/metric evidence отсутствует.

`no_financial_input` — неверно: financial value присутствует.

`unsupported` — неверно: supported normalized-table shape.

`unclassified_financial_input` — единственный safe result.

### Downstream effect of observed typed cash

Observed decision не связал source label и создал cash state из
amount/date/currency/scope shape. Financial context:

- получает canonical cash input type;
- имеет пустой literal-source-label set;
- не несёт positive cash evidence.

Это semantic misclassification, не representation alias.

Expected unclassified uniquely required: yes.

## Comparator assessment

Current product comparator правильно фиксирует:

- literal loss;
- inventions;
- duplicate/cross-scope bindings;
- terminal ownership;
- deterministic context integrity;
- expected disposition/type mismatch.

Но generic preservation invariants сами по себе не доказывают safe type
admission. В v2 benchmark нужны отдельные checks:

- typed branch был pre-admitted;
- admission evidence hash/policy совпадает;
- ambiguous scope не содержит typed branch;
- selected type имеет unique positive evidence;
- unclassified сохраняет все candidate values.

Exact internal graph не нужен.

## Overconstrained/under-grounded expectation audit

Для двух disputed cases:

- overconstrained expectations: 0;
- fixture expected changes: 0.

Выявлен adjacent v1 benchmark defect:
`syn_successor_missing_optional` ожидает typed cash при отсутствии visible
positive cash discriminator. Amount/date/currency shape недостаточен по
Registry definition.

Benchmark v2 должен выбрать одно:

1. добавить authoritative, package-owned cash evidence и сохранить typed
   expectation; или
2. сохранить отсутствие discriminator и ожидать unclassified.

Нельзя использовать expected answer/admission flag, созданный только ради
зелёного fixture.

## Benchmark v2 grounding requirements

Каждый case должен явно моделировать source evidence, а не fixture naming:

- uniquely typed: positive discriminator + unique association;
- multiple compatible types: competing evidence, no unique association;
- no Registry type: financial content без positive predicate;
- missing discriminator: unclassified;
- sufficient discriminator: typed;
- total/detail: authoritative row/header structure;
- adjacent values: explicit source grouping;
- unsupported: source-profile contract evidence.

Expected data не передаётся модели.

## Acceptance

- `BENCHMARK_EXPECTATIONS: PRODUCT_GROUNDED`
- `DISPUTED_OVERCONSTRAINED_EXPECTATIONS: ZERO`
- `ADJACENT_V1_EXPECTATION_DEFECT: IDENTIFIED`
- `FIXTURE_CHANGE_JUSTIFICATION: DEFINED_FOR_BENCHMARK_V2`

No production/runtime code changed. Provider/customer calls: 0.
Следующий шаг: Goal 7 final root-cause/refactoring decision.
