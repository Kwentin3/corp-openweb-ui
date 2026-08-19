# Broker Reports G5.45 — Declaration Model & Assembly Audit

Дата: `2026-08-14`

Статус: `DECLARATION_MODEL_ASSEMBLY_PROVEN`

## Итог

Для bounded-профиля `3-НДФЛ / 2025 / Russian-source broker securities /
payable` машинная модель декларации доказана целиком. Полный controlled input
проходит обычный путь source facts → typed contracts → reviewed methodology →
Tax Models → resolved package → released declaration values → consumer-first
projection → официальный XSD. Прямого заполнения final DTO и semantic bypass
нет.

Получены все требуемые terminals:

```text
DECLARATION_CONSUMER_MODEL_PROVEN
DECLARATION_SEMANTIC_MODEL_COMPLETE
END_TO_END_DECLARATION_ASSEMBLY_PROVEN
DECLARATION_VALUE_TRACEABILITY_PROVEN
CROSS_DOMAIN_DECLARATION_CONSISTENCY_PROVEN
```

Это controlled proof, не реальная декларация налогоплательщика и не
продуктовая активация.

## Consumer-first результат

Аудит начат от official target. В controlled XML имеется 49 emitted value
occurrences:

- 44 — все и только released semantic leaves;
- 4 — официальные константы hash-pinned Projection Definition;
- 1 — electronic file ID, принадлежащий target mechanics/filing context;
- 0 — unknown origin;
- 0 — unowned value;
- 0 — unconsumed released semantics.

Для каждого occurrence runtime receipt сохраняет target path/value hash,
Projection Definition mapping, resolved semantic path/value hash, origin kind,
единственного owner и authority/evidence либо methodology/input hashes.
`origin_count >= 1` и `methodology_or_direct_binding_known = true` выполнены
для всех 49 значений.

Отдельно исправлена потеря происхождения taxpayer status: значение и раньше
вычислял residency owner, но release-trace представлял его прямым filing-фактом.
Теперь trace указывает `Gate5ResidencyEvidenceRuntimeFactory.create`, методику
`ru-3ndfl-2025-declaration-input-contract@2026.0-audited` и правило
`taxpayer-residency-article-207-v1`.

## Найденные дефекты и минимальный refactor

1. Consumer projector интерпретировал `budget kind + amount`, сам выбирал
   payable/refundable и создавал нулевой refund. Payable/refundable перенесены
   к существующему `Gate5DeclarationBudgetOutcomeRuntimeFactory`; projector
   теперь только читает готовые значения.
2. Released value contract содержал три значения без target consumer:
   signer identity, budget kind и source-party kind. Они сохранены в sealed
   components/evidence envelope, но удалены из released declaration values.
   Контракт сократился до точных 44 consumer leaves.
3. Controlled fixture передавал residency status сразу в несколько downstream
   inputs. Теперь он содержит только authenticated-style residency evidence;
   классификация выполняется один раз existing residency owner и затем
   передаётся через его typed methodology binding.
4. Старый trace показывал только 10 вручную выбранных critical values. Новый
   opt-in audit receipt связывает все 49 target occurrences с точным origin.
5. Frozen preparation verifier имел устаревший whitelist terminals после
   G5.44. В него добавлен уже существующий
   `RESIDENCY_EVIDENCE_BOUNDARY_PROVEN`; production calculation не менялся.

Новых engine/DSL/DB/workflow/projection framework не создано.

## A–I black-box proof

| Test | Результат |
| --- | --- |
| A | полный controlled case собран; released semantics complete; XML XSD-valid |
| B | удаление residency evidence даёт точный `MISSING_EVIDENCE` blocker; audit receipt/XML release отсутствуют |
| C | удаление/изменение non-semantic release audit metadata не меняет target bytes |
| D | proceeds `+100` меняет ровно восемь ожидаемых mappings: budget payable, total/taxable income, tax base, calculated/payable tax, source income и securities gross income |
| E | одинаковые declaration values с разными audit/release receipt identities дают byte-identical target |
| F | raw semantic input в consumer-first audit route отвергается; маршрут вызывает только `project_released` |
| G | при отсутствии foreign income foreign obligation terminally not activated, вопросов и target mappings нет |
| H | доказанный foreign-source component активирует только foreign obligation, а Russian obligation не активирует |
| I | все 49 emitted values имеют owner и известную methodology/direct binding |

Projection допускает только `MAP`, `FORMAT`, `ENCODE`, `REPEAT`, `PLACE`,
`SERIALIZE`, `VALIDATE`. Tax calculation, residency decision, evidence
selection, FIFO, deductibility и missing-value repair в нём отсутствуют.

G5.45 audit route является release-only. Исторический legacy product authority
не заменён: cutover/activation не были разрешены. Byte parity доказана как
контроль совместимости, а не как публикация нового product path.

## Conditional scope

В основном controlled case:

```text
obl_russian_source_taxable_income = RESOLVED
obl_foreign_source_taxable_income_and_foreign_tax = NOT_ACTIVATED_FOR_SUPPLIED_CASE
foreign target mappings = 0
unrelated conditional domains activated = 0
```

Отдельный foreign control доказывает точную обратную активацию только foreign
obligation. Полный foreign projection не заявлен: treaty-specific foreign tax
credit остаётся legal-methodology gap.

## Frozen real case replay

Controlled proof отделён от повторного read-only real replay. Frozen corpus:
4 документа, 186 financial source facts, 15 metadata facts, 25 Definition
demands, из них 9 active и 16 suppressed. Результат ожидаемо
`PREPARATION_INCOMPLETE`; XML не выпущен.

Active terminal counts:

```text
MISSING_EVIDENCE = 4
SOURCE_EVIDENCE_INSUFFICIENT = 1
METHODOLOGY_UNRESOLVED = 4
MODEL_GAP = 0
UNKNOWN_INPUT_PATH = 0
UNOWNED_DECLARATION_VALUE = 0
```

Остаются 12 required actions: 8 `ADDITIONAL_DOCUMENT`, 4 `USER_FACT`.
Calculations — 0, provider calls — 0, invented facts/relations — 0. Frozen
store до/после идентичен. Private payload и значения сохранены только вне Git;
safe evidence не содержит локальных путей или частных значений.

## Regression evidence

- обязательная G5.45 A–I матрица: `8 passed`;
- focused E2E/release/G5.44 invariants: `192 passed`;
- все Gate 5 modules: `461 passed`;
- все 15 Gate 3/4 modules: `150 passed`;
- rebuilt bundle + isolated/control XML vertical: `17 passed`, 5 сторонних
  SWIG deprecation warnings;
- `python -m compileall`: `PASS`;
- scoped whitespace check на G5.45 paths:
  `PASS_WITH_LINE_ENDING_WARNINGS_ONLY`.

## Open legal gaps и scope stop

Без догадок сохранены:

```text
ambiguous_security_disposal_source_classification
partial_acquisition_commission_allocation
non_rub_intermediate_precision_and_rounding
treaty_specific_foreign_tax_credit_limit
```

Product activation, legacy authority cutover, real-case declaration release,
commit, push и PR не выполнялись. G5.45 закрыт на доказанном bounded profile;
следующий GOAL автоматически не начинается.
