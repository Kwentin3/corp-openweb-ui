# Broker Reports Gate 5 — Declaration Projection Spec (G5.12)

Date: 2026-08-09

Goal status: `G5.12_CLOSED`

Verdict: `PROVEN`

Product status: `INACTIVE PROOF`

## Ответ

**Да.** Из authoritative требований одной версии 3-НДФЛ агентом получен
маленький machine-readable Declaration Projection Spec. Обычный runtime
детерминированно валидирует candidate против отдельного evidence pack и
исполняет его без знания налоговой методологии и без LLM в case-time.

Доказан только один fragment:

```text
3-НДФЛ за 2025 год
Приложение 8
Файл/Документ/НДФЛ3/ДохОперЦБ
поля строк 010-050
```

Результат является declaration-shaped fragment, структурно согласованным с
релевантным XSD-контрактом. Это не полный XML и не заявление о полной XSD
validity.

## Найденный минимальный seam

```text
[ Official FNS Form / Procedure / Format / XSD ]
                    |
                    v
        [ bounded agent research ]
                    |
                    v
     [ exact SHA-pinned Evidence Pack ]
                    |
                    v
       [ candidate Projection Spec ]
                    |
                    | closed validation
                    v
        [ deterministic projector ]
                    |
                    v
       [ Appendix 8 logical fragment ]
```

Запрещённые переходы остались отсутствующими:

```text
Tax Methodology ──X──> XML names
Projection Spec ──X──> tax calculation
LLM ──X──> case-time declaration generation
```

Публичная граница одна:

```python
Gate5DeclarationProjectionRuntimeFactory.create(...)
```

Factory всегда загружает один exact SHA-pinned repository evidence pack,
валидирует repository или authoring-time candidate и только затем возвращает
projector. `project(...)` читает лишь validated spec и synthetic proof input.

## Bounded research task для агента

Агенту был дан не весь Gate 5, а закрытый вопрос:

```text
Для формы 3-НДФЛ за 2025 год по приказу ЕД-7-11/913@
найти только representation пяти готовых semantic values
в одном элементе Appendix 8:

operation_category
operation_category_gross_income
related_expenses
allowable_expenses
loss_treatment

Допустимые sources:
official form + filling procedure + electronic format + XSD.

Выход:
candidate mapping + exact evidence references.

Не определять налоговый смысл, допустимость расходов или сумму налога.
```

Candidate сформирован без GUI-конструирования mapping'ов и сохранён как
[machine-readable spec](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_projection_spec.ru_3ndfl_2025_appendix8.v0.json).

## Authoritative evidence

Точный target повторно проверен 2026-08-09 по
[официальной карточке приказа ФНС](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/).
Карточка подтверждает приказ `ЕД-7-11/913@`, КНД `1151020`, три приложения и
применение начиная с декларации за 2025 год.

Official bytes получены повторно; hashes совпали с captured evidence pack:

| Source | Bytes | SHA-256 | Used locator |
| --- | ---: | --- | --- |
| [форма, приложение 1](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf) | 438785 | `d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565` | Appendix 8, lines 010-050 |
| [порядок, приложение 2](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx) | 106008 | `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc` | paragraphs 6, 97-98; Appendix 8 code 01 |
| [электронный формат, приложение 3](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_3.docx) | 148677 | `f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2` | table 4.46 |
| [XSD 5.20](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd) | 178427 | `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` | `ДохОперЦБ` definition |

Captured evidence не полагается на prose G5.10 как на нормативный authority.
Его repository representation находится в
[evidence pack](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_projection_evidence.ru_3ndfl_2025_appendix8.v0.json),
raw DOCX/PDF/XSD в Git не добавлялись. Exact evidence resource дополнительно
закрыт SHA-256
`36d301bb9666d0f61213ccce95b016e7a674d30d1e0841cea0d8ebc59977f4d7`.

## Что подтвердили official sources

Порядок, пункт 98:

| Form line | Meaning |
| --- | --- |
| 010 | operation type code по приложению 8 к порядку |
| 020 | общая сумма дохода по совокупности операций |
| 030 | связанные расходы на приобретение/реализацию/хранение/погашение |
| 040 | расходы, принимаемые в уменьшение доходов |
| 050 | признак учёта убытков; `0` означает, что убыток не учитывается |

Приложение 8 к порядку связывает stable meaning «обращающиеся на
организованном рынке ценные бумаги вне ИИС» с declaration code `01`.

Формат, таблица 4.46, и XSD дают:

| Attribute | Use | Representation |
| --- | --- | --- |
| `ВидОпер` | required | string length 2 |
| `ДохСовОпер` | required | decimal, total 14, fraction 2 |
| `РасхРеалЦБ` | optional | decimal, total 14, fraction 2 |
| `РасхУмДохОпер` | optional | decimal, total 14, fraction 2 |
| `ПризУчетУбыт` | required | string length 1, `0` or `1` |

Сам `ДохОперЦБ` имеет XSD cardinality `0..unbounded`. Proof создаёт одну
logical occurrence; full declaration envelope не строится.

## Минимальный Projection Spec

Spec отделяет stable concepts от version-specific representation:

| Stable proof-input concept | Declaration target | Transform owner | Evidence |
| --- | --- | --- | --- |
| `operation_category` | `ДохОперЦБ@ВидОпер` | enum mapping in spec: representative value -> `01` | form lines, procedure 98, procedure code table, format 4.46, XSD |
| `operation_category_gross_income` | `@ДохСовОпер` | RUB money amount, scale 2 | form lines, procedure 6/98, format 4.46, XSD |
| `related_expenses` | `@РасхРеалЦБ` | RUB money amount, scale 2 | form lines, procedure 6/98, format 4.46, XSD |
| `allowable_expenses` | `@РасхУмДохОпер` | RUB money amount, scale 2 | form lines, procedure 6/98, format 4.46, XSD |
| `loss_treatment` | `@ПризУчетУбыт` | enum mapping in spec: `none` -> `0` | form lines, procedure 98, format 4.46, XSD |

`01`, `0` и все русские XML names принадлежат spec/evidence artifacts. Они не
являются именами внутренних Tax Model categories и отсутствуют в projector
control flow.

## Synthetic consumer input

Production Tax Model в G5.12 не создавался. В proof использован явно
неавторитетный consumer stub:

```json
{
  "operation_category": "organized_market_securities_outside_iis",
  "operation_category_gross_income": {"amount": "100.00", "currency": "RUB"},
  "related_expenses": {"amount": "72.00", "currency": "RUB"},
  "allowable_expenses": {"amount": "72.00", "currency": "RUB"},
  "loss_treatment": "none"
}
```

Stub не сохраняется и не объявлен будущей production Tax Model schema.

## Deterministic result

Один и тот же input через новый runtime дал byte/structure-equal replay и
следующий logical fragment:

```json
{
  "target": {
    "path": "Файл/Документ/НДФЛ3/ДохОперЦБ",
    "element": "ДохОперЦБ",
    "occurrence": 1
  },
  "attributes": {
    "ВидОпер": "01",
    "ДохСовОпер": "100.00",
    "РасхРеалЦБ": "72.00",
    "РасхУмДохОпер": "72.00",
    "ПризУчетУбыт": "0"
  }
}
```

Full result также содержит пять mapping-level provenance records и bindings:

```text
spec_sha256 = 89a210b87f5bc275b85357d5390c046f13bd4b19723ca21e59020b34efae3f24
evidence_pack_sha256 = 36d301bb9666d0f61213ccce95b016e7a674d30d1e0841cea0d8ebc59977f4d7
```

## Deterministic validation и fail closed

Validator не содержит второй список XML mappings. Required targets,
datatypes, evidence requirements и supported code claims читаются из exact
evidence pack.

| Negative case | Result |
| --- | --- |
| unknown source concept | `gate5_declaration_projection_unknown_source_concept` |
| missing required mapping | `gate5_declaration_projection_missing_required_mapping` |
| target path/attribute outside captured contract | `gate5_declaration_projection_invalid_target` |
| code without exact mapping claim | `gate5_declaration_projection_unsupported_code` |
| duplicate source/target mapping | `gate5_declaration_projection_conflicting_mapping` |
| incomplete evidence refs | `gate5_declaration_projection_evidence_incomplete` |
| missing/invalid input or unsupported enum/currency | explicit input error; no fragment |

Ни один reject path не создаёт best-effort result.

## Anti-hardcode proof

Static AST/source test проверяет, что maintained Python projector не содержит:

```text
Файл/Документ/НДФЛ3/ДохОперЦБ
ВидОпер
ДохСовОпер
РасхРеалЦБ
РасхУмДохОпер
ПризУчетУбыт
organized_market_securities_outside_iis
```

Projector исполняет две минимальные representation primitives из validated
spec: stable-enum -> declaration code и money -> decimal amount. Налоговых
ветвлений и securities-specific control flow нет.

## Ownership table

| Knowledge / behavior | Owner |
| --- | --- |
| tax meaning | Tax Methodology |
| stable calculated value | Tax Model |
| declaration code/path/cardinality | Declaration Projection Spec |
| official proof of mapping | Evidence Pack |
| mechanical mapping execution | deterministic projector |
| research/extraction | LLM agent |

Responsibilities не дублируются: Evidence Pack объясняет, почему mapping
подтверждён; Projection Spec определяет, что исполнять; projector не решает ни
первую, ни вторую задачу.

## GUI / chat-as-authoring-surface

Proof подтверждает ограниченную гипотезу: для небольшого versioned fragment
специализированный GUI-конструктор mappings не обязателен. Практичный flow:

```text
bounded user request
-> agent research over official sources
-> candidate JSON diff
-> deterministic validation
-> human review / repository publication
```

Chat может быть authoring surface, но не authority и не case-time executor.
Human review/publication остаются обязательными. Для больших форм GUI diff или
review tooling может стать удобным, но G5.12 не доказывает его ненужность в
универсальном масштабе и не реализует его.

## Verification

Shell: Windows PowerShell; Python environment from the service checkout; no
test ENV required.

| Check | Result |
| --- | --- |
| focused G5.12 behavior/architecture | `10 passed` |
| all `test_broker_reports_gate5_*.py` | `38 passed` |
| architecture suite | `29 passed` |
| full service suite, initial run | `2998 passed, 5 skipped, 2 failed, 11 errors` in `15:10` |
| authorized-successor generator after exact hash repair | passed; `provider_calls_total=0`, `runtime_changes_total=0` |
| affected historical audit suite after repair | `13 passed, 1 skipped` |
| Ruff check / format check | passed |
| package-only closed-world simulation | runtime constructed; module + both JSON resources present |
| official source byte/hash refresh | all four hashes matched |
| `git diff --check` | passed before report finalization |

Tests assert observable fragment/error outcomes; unit-under-test and core
logic are not mocked. There is no irreversible boundary: the runtime has no
persistence, provider or network side effect. The exact factory route is
covered by the `FACTORY_REQUIRED` anchor and focused source/AST assertions.

The full suite reached a real terminal outcome; it did not time out. Eleven
errors were caused by the expected managed authority-map hash mismatch after
the documented authority change. Only the existing authorized-successor hash
was updated, after which the generator check and all 13 affected tests passed.

The two remaining full-suite failures are separately attributed and were not
hidden:

1. `test_nine_label_definitions_are_not_copied_into_python_or_prompts` finds
   pre-existing `SECURITY_DISPOSAL` in package `__init__.py`; the exact symbol
   is already present at the G5.11 base commit and was not added by G5.12.
2. `test_17_new_package_module_is_declared_and_ci_runs_this_suite` compares the
   whole stacked branch against `origin/main`; its allowlist already omitted
   several earlier G5.2-G5.11 modules, and now also reports the G5.12 module.
   Fixing the accumulated historical allowlist is a separate cleanup and was
   not used to weaken or reshape this proof.

No assertion failure was attributed to the G5.12 behavioral, fail-closed,
factory, evidence-binding or architecture tests.

## KISS и scope stop

Добавлены только:

- one validator/projector module;
- one candidate spec JSON;
- one exact evidence pack JSON;
- one focused test module;
- one versioned contract and this report;
- one architecture-authority row.

Не созданы Tax Model, Tax Engine, generic form engine, DSL, XML serializer,
database/table/repository, managed publication, workflow, GUI, provider route
или product activation. Gate 4 и G5.11 не изменялись.

G5.12 закрыт. Следующий Gate 5 slice не начинался.
