# G5.39R — Source-authored Financial Event Relation Research

Terminal: `NO_RELATION_STRATEGY_PROVEN`
Blocker: `UPSTREAM_STRUCTURE_RELATION_LOSS`
Date: `2026-08-12`
Mode: research only; production implementation and G5.40 were not started.

## Ответ

На frozen G5.39 corpus source-derived structure **не дала production-grade
relation witness** для распределённых DEV и large-real events.

Четыре стратегии прошли hard safety (`false relations = 0`, A/B cross-join =
`0`), но ни одна не прошла обязательную комбинацию DEV + independent real
holdout:

- R1/R4 доказали relation только там, где source relation был явно сохранён в
  controlled A/B fixture;
- R2 корректно доказала единственный row-local real holdout, но не закрыла
  multi-row/multi-table events;
- R3 не нашла target-granular repeated identity или полный exact composite и
  честно вернула `UNRESOLVED` во всех четырёх cases.

Поэтому winner и partial winner отсутствуют. `G5.40 — Clean Structural
Relation Implementation` **не разрешён**.

## Frozen baseline и corpus

Product repository на входе уже был dirty:

```text
HEAD       02659a9b0bdfb2f19171d2a070a660af85119d59
HEAD tree  0a696522eb37eca13bb9224a41f7227823c8ce8c
```

Турнир выполнялся в отдельном ignored nested Git repository:

```text
baseline commit  93dbfbb89ddd5ae75627ea590cc9cf26e8892246
baseline tree    4b86762cbe40b6cffd38737247bf6687392c1392
```

Frozen corpus не менялся после G5.39:

```text
safe manifest SHA-256
dc9619eb446c01c82cbce538e01c70be7c170c25da95c4ef230efce217d61c2d

private reviewed corpus/oracle SHA-256
d76ade254cfe2c323e0ab73daf0fcf83d598034022e096dba6c86173a65e6c85
```

Preregistration был сохранён до hypothesis implementation и source-value
inspection. Его SHA-256:

```text
de7c206fa103139ace2ca5c730e1fa9c443f32f2eabd2d9118482b996cdab112
```

## Oracle-independent runtime evidence

Private corpus был физически разделён на два файла:

```text
oracle-free runtime SHA-256
b840856d776b419851fd482b1da03cdde7deaea468c4201cd7a551a0835fd744

private evaluator SHA-256
661a1165422a218fe278a191beec699672f153b742df07f178f86055f6401ef8
```

Runtime leak scan: `0`. Strategy process не видел:

```text
expected
event_group
required_evidence_refs
forbidden_mixed_refs
financial type
role profile
```

Каждая strategy сначала записала immutable proposal document; только после
этого отдельный evaluator открыл oracle. Повторный прогон всех proposal
documents дал byte-identical SHA-256.

Relation correctness не использовала LLM: provider calls `0`, retry `0`,
repair `0`, best-of-N `false`, merge `false`.

## Relation comparison matrix

| Strategy | Commit | DEV | Real holdout | Large real | A/B | False joins | Precision / recall | Verdict |
|---|---|---|---|---|---|---:|---:|---|
| R1 explicit source identity | `b628c29` | unresolved | unresolved | unresolved | **correct** | 0 | 1.00 / 0.25 | reject: synthetic-only |
| R2 source structural container | `e1e4583` | incomplete | **correct** | incomplete | incomplete | 0 | 0.25 / 0.25 | reject: row-local only |
| R3 exact deterministic constraints | `8067934` | unresolved | unresolved | unresolved | unresolved | 0 | n/a / 0.00 | reject: identity absent/incomplete |
| R4 hybrid minimal witness | `b7e1cce` | unresolved | unresolved | unresolved | **correct** | 0 | 1.00 / 0.25 | reject: synthetic-only |

Proposal/evaluation hashes and complete aggregate metrics are in the safe
ledger beside this report.

## R1 — Explicit Source Identity

R1 accepted only explicit source relation edges or already typed source
identity attributes. It did not infer identity from equal text or header names.

Result:

- A/B contained two explicit cell-to-cell relation edges and produced one
  correct two-row witness;
- DEV, real holdout and large real contained no explicit relation edge;
- real holdout had an identity-looking anchor value, but that exact identity
  occurred in one row only and therefore related nothing;
- no real-document multi-row witness was produced.

R1 is safe but has no useful real distributed-event coverage. Synthetic-only
coverage cannot select a partial winner.

## R2 — Source Structural Container

R2 used the smallest source-authored event-granular container: one row and its
cells. Ordinary table/page membership was deliberately excluded.

Result:

- independent real holdout was genuinely row-local: `1` oracle event row,
  `9` required refs; R2 was correct;
- DEV required `9` related rows and `24` refs; the anchor row was incomplete;
- large real required `3` related rows and `17` refs; the anchor row was
  incomplete;
- A/B required two explicitly related rows; one row was incomplete.

R2 independently reproduces the safe domain of G5.39 H1. It is useful but does
not answer the distributed-event research question and gives no practical
advantage over the frozen fail-closed baseline.

## R3 — Exact Deterministic Identity Constraints

R3 used one frozen broker-neutral header vocabulary. It admitted either:

```text
unique repeated explicit event identity
```

or the complete exact composite:

```text
instrument + quantity + operation datetime + source-side reference
```

Raw literal/numeric equality could not create membership. Arithmetic was only
eligible as post-selection consistency evidence.

Target audit:

- DEV anchor exposed none of the frozen identity kinds;
- real-holdout anchor exposed one explicit identity value, but its row
  frequency was exactly `1`; its composite contained only quantity;
- large-real anchor exposed none of the identity kinds;
- A/B anchor exposed quantity only; relation lived in explicit edges, not an
  identity composite.

Thus R3 returned four bounded `UNRESOLVED` outcomes and no false relation.

## R4 — Hybrid Minimal Witness

R4 required two independent source-authored families:

- explicit relation plus closed row containers; or
- at least two exact identity attributes plus exact Decimal consistency.

It proved the same explicit A/B event as R1. No real target supplied the
required hybrid. The arithmetic-only negative test confirmed that an exact
numeric equality cannot mint event identity.

## False-join audit

All four strategies:

```text
false relations    0
cross-event joins  0
invalid refs       0
silent first-match 0
```

The A/B positive event was correctly closed only by R1/R4 using the two
explicit source edges. R2 stayed within A's anchor row and was incomplete. R3
declined. No strategy joined Transaction A and Transaction B.

Fail-closed behavior was preferred over recall throughout.

## Holdout и large-document pressure

Independent real holdout proved the narrow positive boundary: a source row can
be sufficient when the event is objectively row-local.

Large real remained bounded and deterministic. R1/R3/R4 scanned/indexed
source structure without model context; R2 examined only the anchor row. No
strategy passed a 500k-character document to an LLM. The large target's
source-derived representation contained row/cell/page/table boundaries and 57
table date ranges, but no event-granular relation edge, repeated target
identity or nested container for its three oracle rows. Same page/table/date
range was not promoted to identity.

## Structural-limit conclusion

For the distributed DEV and large-real targets, the frozen representation
preserves exact structural refs and local containers but does not preserve the
human-reviewed economic-event membership relation.

Это локализуется как:

```text
UPSTREAM_STRUCTURE_RELATION_LOSS
```

Вывод ограничен frozen corpus и текущей source-derived representation. Он не
утверждает, что любой broker/source никогда не содержит explicit relation.
Напротив, A/B показывает: когда relation действительно присутствует и
сохраняется структурно, минимальный witness работает. Но на real distributed
cases такой evidence не сохранён.

## Role/product pressure

Статус:

```text
NOT_RUN_NO_RELATION_FINALIST
```

Ни одна strategy не прошла DEV + independent real holdout relation boundary,
поэтому запуск role model нарушил бы preregistration. Provider calls `0`.

Production-equivalent Gate 3 owner остаётся неизменным:
`Gate3RoleLabelingFactory.create_from_chunk`; experimental direct-provider
route не создавался.

Неизменённые product regressions:

```text
python -m pytest -q \
  tests/test_broker_reports_gate5_coverage_expansion.py \
  tests/test_broker_reports_gate5_related_securities_events.py \
  --tb=short

8 passed in 3.89s
```

Они сохраняют CSV/HTML/XLSX convergence, related-securities behavior,
declaration semantics и valid XML pressure. Product Gate 4+, Tax Models,
Declaration Definition, Package, Semantic Input, projection и XML не менялись
в G5.39R.

## Complexity и KISS

| Strategy | Experimental strategy LOC | New production schemas | New persistence |
|---|---:|---:|---:|
| R1 | 113 | 0 | 0 |
| R2 | 47 | 0 | 0 |
| R3 | 100 | 0 | 0 |
| R4 | 143 | 0 | 0 |

R2 — самая простая полезная стратегия, но её доказанный domain уже совпадает с
row-local fail-closed baseline. R1/R4 показывают здравое зерно explicit relation
when present, но только на synthetic case. Сложность не может выбрать winner
при отсутствии required real coverage.

Новая DB, graph, index persistence, rules engine, broker template, semantic
search или CanonicalArtifact refactor не создавались.

## Tests и integrity

Research tests в Windows PowerShell:

```text
common evaluator  4 passed
R1 total          6 passed
R2 total          5 passed
R3 total          6 passed
R4 total          6 passed
```

Тесты проверяют observable terminal outcomes: correct, incomplete,
false-relation hard failure, unresolved, exact-source positive, untyped literal
negative и arithmetic-only negative. Unit under test не мокался; external
provider boundary отсутствовал. Необратимой boundary в relation experiment
нет: только private proposal file создаётся до read-only adjudication.

## Research cleanup

- R1–R4 experiment commits и hashes зафиксированы в safe ledger.
- Все proposal/evaluation exact bytes сохранены только под ignored `local/`.
- Все четыре worktree и experiment branches удалены после фиксации evidence.
- Nested experiment Git repository удалён.
- Rejected/winner experimental code в product tree не осталось.
- В product tree остались только preregistration, safe ledger, receipt и этот
  report.
- Commit, push, PR и product activation не выполнялись.

## Research journal

Один GitHub issue создан и обновляет единую историю G5.38C → G5.39 → G5.39R:

```text
https://github.com/Kwentin3/corp-openweb-ui/issues/278
```

## Winner contract / no-winner explanation

Ни одна из четырёх стратегий не выполняет strong winner requirement. Partial
explicit-when-present strategy также не выбрана: её единственный positive
case synthetic, а полезная real-document coverage отсутствует.

Финальный ответ:

```text
NO_RELATION_STRATEGY_PROVEN
UPSTREAM_STRUCTURE_RELATION_LOSS
```

## Next authorization

```text
G5.40 — Clean Structural Relation Implementation
NOT AUTHORIZED
```

Следующий production GOAL не разрешён. Отдельный будущий research GOAL может
исследовать только upstream preservation of source grouping/identity, если
появится новый source artifact или новый structural evidence; G5.39R не
разрешает CanonicalArtifact redesign, human confirmation UX или очередную
retrieval heuristic.
