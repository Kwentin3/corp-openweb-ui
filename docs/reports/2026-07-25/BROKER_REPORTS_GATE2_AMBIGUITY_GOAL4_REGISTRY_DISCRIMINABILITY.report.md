# Broker Reports — Gate 2 ambiguity discipline, Goal 4

Дата: 2026-07-25

Статус: `REGISTRY_DISCRIMINABILITY: MACHINE_GAP_IDENTIFIED`

## Result

Два Registry types концептуально различимы:

- `cash_balance_snapshot_v1` — source-stated ordinary cash-class balance на
  reporting date/scope;
- `printed_financial_metric_v1` — financial total/metric, явно напечатанный
  source для date/period/scope и не рассчитанный Gate 2.

Textual definitions, provider descriptions и counterexamples уже проводят
правильную semantic boundary. Новый type для disputed fixtures не нужен.

Но Registry v1 не выражает эту boundary как machine-readable typed-admission
contract.

## cash_balance_snapshot_v1

### Adequate existing semantics

- state semantic class;
- explicit reporting date/scope;
- ordinary cash requirement;
- exclusion regulated/segregated balances без ordinary-cash classification;
- source sign preserved;
- counterexample для cash movement.

### Machine gap

Required roles:

- amount;
- as-of date;
- statement scope.

`source_label` и `balance_class` optional. Поэтому generic amount/date/scope
полностью удовлетворяет strict typed schema без evidence, что source вообще
назвал значение cash.

Registry definition говорит «source-stated cash», но schema не требует ref,
который доказывает это условие.

## printed_financial_metric_v1

### Adequate existing semantics

- aggregate semantic class;
- printed, not Gate-2-calculated distinction;
- explicit reporting scope и date/period;
- required printed-label evidence;
- counterexamples для calculated aggregate и repeated representation.

### Machine gap

Required `printed_label_evidence_ref` структурно существует, но current
deterministic factory синтезирует его для каждого scope. Registry не различает:

- identity/link ref;
- доказательство, что visible source label является printed total/metric.

`forbidden_roles` запрещают calculation/component roles, но не выражают
forbidden semantic evidence.

## Cross-type discriminability

| Dimension | Cash | Printed metric | Machine-enforced now |
|---|---|---|---:|
| Semantic class | state | aggregate | No admission effect |
| Positive source statement | ordinary cash | printed total/metric | No |
| Date/period | date required | date or period | Shape only |
| Label evidence | optional source label | synthesized reference | Insufficient |
| Calculated/detail exclusion | implicit/provider text | explicit text | No |
| Source families | same broad families | same broad families | No distinction |
| Sign policy | preserve | preserve | Not discriminating |

Conceptual definitions mutually discriminate. Current role/schema projection
does not.

## Required admission metadata

Safe typed admission needs versioned, machine-readable declarations:

- positive evidence predicate ID;
- required source-context fields;
- required authoritative association;
- forbidden/ambiguity evidence codes;
- uniqueness rule;
- conservative default: not admitted;
- value-free admission receipt shape.

Эти rules нельзя хранить только в prompt.

## Registry version decision

Registry v1 и immutable type IDs не менять:

- textual meaning корректен;
- изменение required roles сломает accepted contracts;
- новый Registry type был бы fixture-driven;
- налоговая/документная методика Registry не принадлежит.

Минимальное решение:

- новый `TypedAdmissionPolicyV1`, keyed существующими Registry type IDs;
- policy version/hash pin в successor scope v2;
- future Registry version только если admission metadata станет общим
  Registry contract после отдельного доказательства.

Provider descriptions/counterexamples могут быть bounded guidance для model
input v2, но не safety authority.

## Two disputed cases

- multiple hypotheses: обе type definitions одновременно имеют partial
  supporting evidence, ни одна не имеет unique positive proof →
  explicitly ambiguous.
- explicit unclassified: ни cash, ни printed positive semantic condition не
  доказано; generic shape недостаточен → no admitted Registry type.

В обоих случаях correct terminal disposition — unclassified, без создания
фиктивного type.

## Acceptance

- `REGISTRY_TYPES: CONCEPTUALLY_MUTUALLY_DISCRIMINABLE`
- `MACHINE_ADMISSION_BOUNDARY: EXPLICITLY_INSUFFICIENT`
- `DEFINITION_GAPS: MACHINE_READABLE_ADMISSION_METADATA`
- `REGISTRY_EXPANSION: ZERO`
- `REGISTRY_V1_SEMANTIC_DRIFT: ZERO`

No production/runtime code changed. Provider/customer calls: 0.
Следующий шаг: Goal 5 prompt and branch-bias audit.
