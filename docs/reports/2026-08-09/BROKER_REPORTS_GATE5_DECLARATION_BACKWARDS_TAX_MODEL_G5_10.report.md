# Broker Reports Gate 5 — Declaration-Backwards Tax Model (G5.10)

Date: 2026-08-09

Goal status: `G5.10_CLOSED`

Research outcome: `PARTIAL_ARCHITECTURE_MATCH`

Architecture verdict: `MINIMAL_TAX_MODEL_CORRECTION_REQUIRED`

Product status: `INACTIVE`

## Verdict

Если идти назад от действующей 3-НДФЛ за 2025 год, текущий Gate 5 contour
совпадает с нужной архитектурой по механике, но не по завершённой tax semantics.

Уже доказаны полезные seams:

```text
trusted methodology
-> source-tagged input discovery
-> deterministic Decimal behavior
-> reproducible structured result
```

Однако G5.7 пока выдаёт экспериментальные `proceeds`,
`recognized_expense`, `net_result`. Для декларации этого недостаточно:

- `net_result` не является устойчивым Tax Model concept;
- `recognized_expense` смешивает фактические расходы и расходы, допустимые для
  уменьшения дохода;
- отсутствуют tax period, residency, calculation scope, operation/income
  classification, aggregation scope, exemptions/deductions/loss treatment,
  tax base, rate snapshot, calculated tax и source/withholding context;
- отсутствует отдельная projection из Tax Model в форму/XML.

Вывод: **контур переиспользуем, но Tax Model и Tax Methodology должны быть
скорректированы backwards от декларационного смысла. Gate 4 менять не нужно.**

## Research boundary

Исследован один закрытый representative scenario:

```text
налоговый период: 2025
налогоплательщик: физическое лицо, налоговый резидент РФ
операция: обычная продажа одной ценной бумаги
рынок: организованный рынок ценных бумаг
счёт: не ИИС
источник дохода: в Российской Федерации
валюта расчёта: RUB
льгота по пунктам 17.2/17.2-1 статьи 217 НК РФ: неприменима
перенос убытков, инвестиционные вычеты, иностранный налог: отсутствуют
иные доходы/расходы группы 02 и удержанный налог: отсутствуют
```

Для иллюстрации сохранены числа G5.7:

```text
доход от продажи: 100.00 RUB
стоимость приобретения: 70.00 RUB
расход на сделку: 2.00 RUB
```

Это сознательно закрытая гипотеза. Выводы нельзя автоматически переносить на
погашение, частичное погашение, необращающиеся бумаги, ИИС, РЕПО, ПФИ,
инвестиционное товарищество, льготы длительного владения или другой налоговый
период.

## Exact official declaration target

Выбран завершённый налоговый период `2025`. Project context не закрепляет иной
период, а на дату исследования ФНС уже опубликовала отдельную действующую форму
для деклараций за 2025 год.

| Property | Exact target |
| --- | --- |
| tax period | calendar year `2025`; title-page period code `34` |
| declaration | 3-НДФЛ, КНД `1151020` |
| authority | приказ ФНС России от 20.10.2025 № `ЕД-7-11/913@` |
| registration/publication | зарегистрирован Минюстом 31.10.2025 № 84028; официальное опубликование № `0001202510310029` |
| form | приложение № 1 к приказу |
| filling procedure | приложение № 2 к приказу |
| electronic format | приложение № 3; формат `5.20`, часть XXXIII |
| XSD | `NO_NDFL3_1_033_00_05_20_01.xsd`; schema family `NO_NDFL3_1_033_00_05_20_xx` |
| effective boundary | приказ вступает в силу по истечении двух месяцев после официального опубликования, не ранее 01.01.2026, и применяется начиная с декларации за 2025 год |

Приказ одновременно утверждает форму, порядок заполнения и электронный формат.
Это подтверждено [официальной карточкой ФНС](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
и [официальной публикацией НПА](https://publication.pravo.gov.ru/document/0001202510310029).
Страница ФНС с формами отдельно указывает период действия формы, порядка и
формата с 2025 года: [3-НДФЛ на сайте ФНС](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/?p=1210).

Authoritative attachments:

- [форма 3-НДФЛ, приложение № 1 (PDF)](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf);
- [порядок заполнения, приложение № 2 (DOCX)](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx);
- [электронный формат, приложение № 3 (DOCX)](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_3.docx);
- [официальная XSD](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd).

Диагностически загруженные official bytes не добавлялись в repository. Их
snapshot fingerprints на дату исследования:

| Official file | Bytes | SHA-256 |
| --- | ---: | --- |
| filling procedure DOCX | 106008 | `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc` |
| electronic format DOCX | 148677 | `f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2` |
| XSD | 178427 | `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` |

## What the official form requires for this scenario

### Appendix 1 — Russian-source income

Пункты 57–60 порядка требуют отражать доходы от источников в РФ отдельно по
источнику и виду дохода. Для каждой записи нужны код вида дохода, сведения об
источнике, сумма дохода и удержанный налог.

Для выбранной resident securities scenario приложение № 4 к порядку задаёт:

```text
income group code = 02
income type code = 003
rate family = 13/15
```

Смысл кода `003`: налоговая база резидента по операциям с ценными бумагами и
ПФИ вне ИИС и/или соответствующей материальной выгоде, за исключением указанных
льгот статьи 217 НК РФ.

В XML это повторяемый `Файл/Документ/НДФЛ3/ДоходИстРФ` с, в частности:

```text
ВидДоход   <- 003
Доход      <- gross Russian-source income
НалУдерж   <- tax withheld at source
ИстЮЛ / ИстФЛИн <- source identity
```

### Appendix 8 — securities operation category

Пункты 97–98 порядка требуют для операций с ценными бумагами показать не одну
разницу, а отдельную category-level запись:

```text
line 010: operation type code
line 020: total income across the operation category
line 030: expenses related to acquisition, sale, storage or redemption
line 040: expenses accepted to reduce category income
line 050: loss-accounting flag
lines 051/052: loss type and accepted loss, when applicable
```

Приложение № 8 к порядку задаёт для выбранного scenario operation code `01`:
операции с ценными бумагами, обращающимися на организованном рынке, вне ИИС.

В XML это повторяемый `Файл/Документ/НДФЛ3/ДохОперЦБ`:

```text
ВидОпер          <- 01
ДохСовОпер       <- aggregate category income
РасхРеалЦБ       <- related expenses
РасхУмДохОпер    <- tax-accepted expenses
ПризУчетУбыт     <- 0 in the closed scenario
```

`ДохСовОпер` и `ВидОпер` обязательны по XSD. Expense attributes optional at
serialization level, но Tax Model обязан различать отсутствие расхода,
неизвестность и непризнание расхода.

### Section 2 — group tax base and calculated tax

Порядок требует отдельный расчёт Раздела 2 для каждой группы доходов. Для
группы `02` цепочка имеет вид:

```text
line 010 total income
- line 020 exempt income
= line 030 taxable income
- line 040 deductions
- line 050 accepted expenses (including Appendix 8 line 040)
= line 060 tax base
-> line 070 calculated tax
-> line 080 tax withheld
```

Пункты 44–46 порядка отдельно устанавливают расходы строки 050, ограничение
вычетов/расходов величиной облагаемого дохода и расчёт налоговой базы. Для
группы `02` пункт 48 задаёт 13% при базе не более 2,4 млн рублей и 312 тыс.
рублей плюс 15% превышения при большей базе. Сумма налога округляется до полного
рубля по общему правилу порядка.

В XML это `Файл/Документ/НДФЛ3/НалБаза` с `ГрупДоход="02"` и дочерним
`РасчНалБаза`, где обязательны:

```text
СумДох
СумДохНеНал
СумДохНал
СумНалВыч
СумРасх
НалБаза
```

Форма/XSD — projection targets, а не имена Tax Model fields.

## Representative logical projection

Только при всех закрытых assumptions выше illustrative values дают:

```text
gross category income                      100.00 RUB
related acquisition/transaction expenses   72.00 RUB
tax-accepted expenses                       72.00 RUB
taxable income before expenses             100.00 RUB
group-02 tax base                           28.00 RUB
calculated tax at 13%                        3.64 RUB
declaration tax after whole-ruble rounding      4 RUB
```

Logical projection:

| Tax Model value | Declaration target | XML target |
| --- | --- | --- |
| Russian-source income kind `003`, source, gross income 100, withheld 0 | Appendix 1 lines 010, 030–080 | `ДоходИстРФ` |
| operation category `01`, gross income 100 | Appendix 8 lines 010/020 | `ДохОперЦБ@ВидОпер`, `@ДохСовОпер` |
| related expense 72; accepted expense 72 | Appendix 8 lines 030/040 | `@РасхРеалЦБ`, `@РасхУмДохОпер` |
| loss-treatment flag 0 | Appendix 8 line 050 | `@ПризУчетУбыт` |
| group `02`, income 100, exempt 0, deductions 0, expenses 72, base 28 | Section 2 lines 001, 010–060 | `НалБаза@ГрупДоход`, `РасчНалБаза` attributes |
| calculated tax 4; withheld 0 | Section 2 lines 070/080 | `РасчНалПУ@Исчисл`, `@Удерж` |

Это proof логической достижимости, не готовый declaration payload. Для реальной
годовой декларации необходимо доказать полноту taxpayer-wide scope и учесть все
остальные записи той же группы, даже если они не входят в этот experiment.

## Minimal declaration-driven Tax Model

Минимальный Tax Model для scenario должен выражать устойчивый смысл и не
копировать номера строк/XSD names.

| Tax Model concept | Minimal content | Scope/owner |
| --- | --- | --- |
| model binding | schema/version, exact methodology and reference snapshot bindings | Tax Model envelope |
| tax context binding | tax period 2025, jurisdiction RU, resident status, declared calculation scope/completeness | trusted Tax Context |
| income source | domestic/foreign classification, source identity, gross income, withheld tax | case input plus facts |
| securities operation classification | sale; organized-market status; outside-IIS status; exemption applicability | Tax Context + Reference Data + evidence |
| operation category | stable category identity independent of current form code | methodology-derived |
| gross income | category aggregate with currency and provenance | Financial Case -> derived aggregate |
| related expenses | components actually related to acquisition/sale/storage/redemption, with provenance | Financial Case/Supplemental |
| allowable expenses | the subset accepted under the applicable methodology, with decision provenance | methodology-derived |
| loss/deduction treatment | explicit none/applied/unknown, not silent zero | Tax Context + methodology |
| taxable income and tax base | group-scoped amounts with aggregation/completeness scope | derived calculation |
| rate result | exact effective rate schedule binding, pre-round amount and rounded tax | Reference Data + calculation |
| audit provenance | every input source, rule/behavior identity and derivation | existing Gate 5 provenance extended semantically |

Tax Model does **not** need names such as `ДохСовОпер` or line `040`. Those are
owned by a versioned Declaration Projection. Conversely, an XML DTO without the
concepts above would not be a sufficient Tax Model.

## Traceability matrix

Status describes the current repository contour before any G5.10 change.

| Declaration requirement | Official meaning | Tax Model concept | How obtained | Required inputs | Source of inputs | Current system status | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| declaration for period 2025, КНД 1151020 | selects effective form/rules/reference tables | `tax_period`, declaration target binding | trusted context selects exact snapshot | period; jurisdiction | Tax Context; Reference Data | MISSING | DATA: no trusted period/context input; DECLARATION PROJECTION: no target selector |
| Appendix 1 income code `003` | resident securities/PFI income outside IIS under group 02, subject to stated exclusions | `income_category` | applicability/classification rule | residency; asset/operation class; IIS; exemption status | Tax Context; Financial Case/Supplemental; Reference Data | NOT_MODELLED | DATA + METHODOLOGY: current methodology has no applicability/classification |
| Appendix 1 source identity | identifies each Russian payment source | `income_source` | group transactions by source | source jurisdiction; INN/KPP/OKTMO/name or permitted operation description | Financial Case or Supplemental; Tax Context | MISSING | DATA: Gate 4 disposal has no payer/source identity |
| Appendix 1 gross income and withheld tax | income from this source and tax already withheld | `source_gross_income`, `withheld_tax` | aggregate proceeds/withholding for source | disposal amount; linked withholding; source binding | Financial Case; Derived calculation | PARTIAL | DATA/UPSTREAM: proceeds exists; `TAX_WITHHELD` may exist but no proven relation to source/disposal |
| Appendix 8 operation code `01` | traded-market securities operations outside IIS | stable `operation_category` | classification mapped through effective reference snapshot | security identity/market status; IIS status; operation kind | Financial Case/Supplemental; Tax Context; Reference Data | NOT_MODELLED | UPSTREAM/DATA: Gate 4 `asset` and `SECURITY_DISPOSAL` do not prove these distinctions |
| Appendix 8 category income | total income across all operations in category | `operation_category_gross_income` | aggregate all eligible disposal proceeds | complete period/category set; amounts; currency conversion if needed | Financial Case; Tax Context; Reference Data; Derived calculation | PARTIAL | METHODOLOGY/DATA: G5.7 accepts exactly one scalar and has no aggregation/completeness |
| Appendix 8 related expenses | actual expenses linked to acquisition/sale/storage/redemption | `related_expenses[]` and total | classify and attribute expense components | acquisition cost; transaction/storage expenses; relation/evidence; currency | Financial Case/Supplemental; Derived calculation | PARTIAL | DATA/UPSTREAM: supplemental values exist, but relation and composition are not proven by current Gate 4/G5.7 |
| Appendix 8 accepted expenses | expenses legally accepted to reduce category income | `allowable_expenses` | methodology eligibility rule over related expenses | related expenses; evidence; applicability conditions | Supplemental; Tax Context; Reference Data; Derived calculation | NOT_MODELLED | METHODOLOGY: G5.7 addition names the result `recognized_expense` without proving allowance |
| Appendix 8 loss flag | whether current/prior losses are applied | `loss_treatment` | explicit context plus methodology | carryforward choice/data | Tax Context; Supplemental; Reference Data | NOT_NEEDED | Closed scenario fixes `none`; a real declaration must not infer zero from absence |
| Section 2 group code `02` | selects separate securities-income tax-base/rate family | stable `tax_base_group` | map classified income through effective reference snapshot | residency; income category; period | Tax Context; Reference Data | NOT_MODELLED | METHODOLOGY/REFERENCE: code/rate group absent from G5.7 |
| Section 2 total/taxable income | group income less exempt income | `group_gross_income`, `exempt_income`, `taxable_income` | taxpayer-wide group aggregation and exemption rules | all group-02 source income; exemption applicability | Financial Case/Supplemental; Tax Context; Reference Data; Derived calculation | MISSING | DATA/METHODOLOGY: no annual group scope or exemption decision |
| Section 2 deductions/expenses | permitted deductions and Appendix 8 accepted expenses | `group_deductions`, `group_allowable_expenses` | aggregate allowed components, capped as required | operation results; deductions; current loss | Derived calculation; Tax Context; Reference Data | NOT_MODELLED | METHODOLOGY: no group aggregation/cap rule |
| Section 2 tax base | taxable income minus allowed deductions and expenses | `tax_base` scoped to group 02 | deterministic group calculation | taxable income; deductions; allowable expenses | Derived calculation | NOT_MODELLED | METHODOLOGY: `net_result` is not a proven group tax base |
| Section 2 calculated tax | 13/15 schedule and whole-ruble result | `calculated_tax`, rate/rounding binding | apply effective schedule, then declaration rounding | tax base; period; rate snapshot | Reference Data; Derived calculation | NOT_MODELLED | DATA/METHODOLOGY: no rate snapshot, behavior or tax result |
| concrete PDF/XML placement | version-specific representation of the stable model | declaration DTO | pure versioned projection | complete Tax Model; target version | Reference Data; Derived projection | NOT_MODELLED | DECLARATION PROJECTION: no mapper/serializer; correctly outside current G5.7 |

## Current G5.7 result — critical comparison

Repository truth:

- [G5.7 contract](../../stage2/contracts/BROKER_REPORTS_GATE5_METHODOLOGY_CALCULATION.v0.md)
  explicitly says the result is not a complete Russian tax base, payable tax or
  final Tax Model;
- [trusted methodology resource](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_tax_methodology.ru_ndfl_securities_proof.v0.json)
  requests one disposal amount/currency plus acquisition cost and transaction
  expense;
- [deterministic behavior](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_methodology_calculation.py)
  computes only acquisition cost + transaction expense and subtracts that sum
  from proceeds.

| G5.7 field | Declaration-driven assessment | Decision |
| --- | --- | --- |
| `proceeds` | useful raw amount, but one scalar is not category/source/annual gross income | retain as input concept; add aggregation scope |
| `recognized_expense` | name overclaims legal recognition; current behavior only adds two values | replace semantically with `related_expense_components/total`, then derive separately proven `allowable_expenses` |
| `net_result` | coincides with 28.00 only under the closed no-deduction/no-loss/single-operation assumptions | do not promote to Tax Model; replace with explicit category result/tax-base contribution and later group tax base |
| methodology/rule/behavior identity | necessary reproducibility/audit binding | retain |
| input provenance | necessary to distinguish Gate 4 and Supplemental sources | retain and carry into model derivations |

The mismatch is not a Decimal or runtime problem. It is a semantic boundary
problem:

```text
current assumption
  one proceeds - one summed expense = net_result

official requirement
  classified and aggregated income
  - explicitly accepted expenses/deductions/losses
  = group-scoped tax base
  -> effective rate and rounded tax
```

## Tax Methodology derived backwards

For this scenario the minimal methodology needs no DSL or generic Tax Engine.
It needs one closed, reviewed rule package containing:

1. applicability conditions:
   period 2025, resident, sale, traded-market security, outside IIS, no stated
   exemption, Russian-source path;
2. semantic requirements:
   proceeds, currency/date, source identity, security/operation classification,
   acquisition/transaction expense components and evidence, withholding;
3. aggregation scopes:
   by source/income kind for Appendix 1, by operation category for Appendix 8,
   by income group for Section 2;
4. expense treatment:
   related expense is not automatically allowable expense; a named decision
   rule produces the latter;
5. deterministic calculations:
   category totals, taxable income, capped deductions/expenses, group tax base,
   rate application and rounding;
6. bindings to effective Reference Data:
   stable categories -> current codes `01`, `02`, `003`, rate schedule and
   declaration target `5.20`;
7. output contract:
   the stable Tax Model concepts above, not PDF/XML field names.

Current G5.2/G5.5 requirement selection remains useful for scalar inputs, but
the current requirement vocabulary is insufficient for classification,
evidence/relations, aggregation and completeness claims.

## Input ownership

| Input | Correct owner/source | Current fit |
| --- | --- | --- |
| disposal date, asset label, quantity, amount, currency | official `Gate4FinancialCaseRuntimeFactory(...).create()` boundary | AVAILABLE for a role-complete disposal fact |
| acquisition cost and transaction expense absent from broker documents | persistent Supplemental Fact boundary | AVAILABLE mechanically; tax attribution/eligibility PARTIAL |
| tax period, residency, calculation scope/completeness, IIS applicability, explicit no-loss/no-deduction assumptions | trusted Tax Context, supplied/confirmed as case input | MISSING; do not put in Gate 4 or methodology authority |
| sale vs redemption/partial redemption, stable security identity, market status, expense-to-operation relation | Financial Case if upstream ever preserves it; otherwise typed Supplemental/context evidence | PARTIAL/MISSING; current Gate 4 boundary cannot recover it |
| operation/income/group codes, rate schedule, form/version and effective dates | versioned authoritative Reference Data snapshot | MISSING; do not hardcode as timeless runtime constants |
| category/group totals, allowable expenses, base and tax | deterministic Tax Methodology calculation | NOT_MODELLED |
| PDF/XML elements and formatting | versioned Declaration Projection | NOT_MODELLED, correctly separate from Tax Model |

`Tax Context` is now concretely justified. Its minimal owner does not need a
framework yet: the calculation cannot select `003`/group `02`, choose the 2025
rate schedule or assert annual completeness without at least period, residency,
account/applicability and scope data.

## Proven gaps

### DATA GAP

- trusted tax period/residency/calculation scope;
- Russian source/payer identity and source grouping;
- IIS/exemption status;
- stable security market classification;
- acquisition/transaction expense evidence and attribution;
- complete annual group-02 input set and linked withholding.

### METHODOLOGY GAP

- applicability/classification for stable operation and income categories;
- category/source/group aggregation;
- distinction between related and allowable expenses;
- exemption, cap, deduction and loss-treatment rules;
- group tax-base calculation, 13/15 schedule and whole-ruble rounding;
- stable Tax Model output contract.

### UPSTREAM SEMANTIC GAP

Current Gate 4 exposes `SECURITY_DISPOSAL` with date, asset, quantity, amount,
currency and optional unit price. It does not prove:

- sale vs redemption/partial redemption;
- stable instrument identity or organized-market status;
- IIS relationship;
- relation of `TRANSACTION_CHARGE`/`TAX_WITHHELD` to this operation or source.

For the closed experiment these can be explicit typed context/supplemental
inputs. For a general solution this is a real upstream semantic limitation.
G5.10 does not bypass it through CanonicalArtifact/broker reports and does not
authorize a Gate 4 change.

### DECLARATION PROJECTION GAP

There is no versioned mapping from the stable Tax Model to Appendix 1,
Appendix 8, Section 2 or XSD 5.20. This gap belongs after Tax Model calculation;
it is not evidence for changing Financial Case or embedding XML names in tax
calculation.

## Backwards architecture and forward meeting point

```text
[ Official 3-NDFL 2025 requirement ]
  Appendix 1 + Appendix 8 + Section 2 + format 5.20
                         |
                         v
[ Tax Model ]
  context-bound income source/category
  + category gross income
  + related and allowable expenses
  + group taxable income/base
  + rate-bound calculated tax
                         |
                         v
[ Trusted Tax Methodology ]
  applicability + classification + aggregation
  + expense eligibility + deterministic calculations
                         |
                         v
[ Required Inputs ]
  Financial Case + Supplemental Fact
  + Tax Context + Reference Data snapshot
```

Existing forward runtime can meet that chain at the Tax Model boundary:

```text
Financial Case / Supplemental / trusted context / reference snapshot
                         |
                         v
methodology-selected source-tagged inputs
                         |
                         v
named deterministic calculation behavior
                         |
                         v
stable Tax Model
                         |
                         v
versioned declaration projection -> 3-NDFL 2025 / XML 5.20
```

Today the forward chain stops one semantic layer early at experimental
`net_result`. The minimal correction is to make the next behavior output an
explicit declaration-driven Tax Model slice, not to turn Gate 4 into a tax
model and not to place form fields inside methodology.

## One next minimal implementation slice

`G5.11 — Securities Disposal Tax Model V0 proof`:

```text
closed trusted Tax Context for the representative scenario
+ exact Reference Data snapshot binding
+ G5.5 source-tagged values
+ one reviewed declaration-derived methodology behavior
        ->
SecuritiesDisposalTaxModelV0
```

The slice should prove only stable classification, category gross income,
related versus allowable expenses and a group-02 tax-base contribution with
full provenance. It must replace the ambiguous `recognized_expense/net_result`
semantics for this path. It should not yet build XML/PDF, a Tax Context
framework, reference-data service, generic aggregation engine or another Tax
Case platform.

This is the first bottleneck because a declaration projector cannot safely map
the current ambiguous result. The next implementation slice was **not started**
inside G5.10.

## KISS and immutability check

G5.10 added no production code, DB/table, service/repository, runtime route,
Tax Engine, DSL, XML generator, reference service, Tax Context framework or
Gate 4 change. Official DOCX/XSD parsing was diagnostic and remained outside
the repository.

The official Financial Case input remains exclusively:

```text
Gate4FinancialCaseRuntimeFactory(...).create()
```

## Final answer

Начав с реальной 3-НДФЛ за 2025 год, системе нужен минимальный Tax Model,
который хранит context-bound classification дохода/операции, агрегированный
доход, связанные и отдельно допустимые расходы, group-scoped taxable income и
tax base, rate/reference binding, исчисленный налог и provenance. Tax
Methodology должна владеть applicability, classification, aggregation,
expense-eligibility и расчётными правилами; Financial Case, Supplemental Fact,
Tax Context и Reference Data должны оставаться различимыми источниками.

Текущий Gate 5 contour соответствует этому направлению **частично**: discovery,
persistence, trusted methodology authority, deterministic behavior и
provenance переиспользуются. G5.7 result не соответствует минимальному Tax Model
семантически и требует указанной локальной коррекции. `G5.10_CLOSED`; следующий
slice только назван, но не начат.
