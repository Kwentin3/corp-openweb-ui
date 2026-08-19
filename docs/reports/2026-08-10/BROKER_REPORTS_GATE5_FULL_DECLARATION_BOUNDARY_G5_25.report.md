# Broker Reports Gate 5 Full Declaration Boundary Research — G5.25

Date: 2026-08-10

Status: `G5.25_CLOSED`

Outcome: `KEEP_FIVE_PRIMITIVES`

Product status: `INACTIVE RESEARCH`

Implementation status: `NOT_STARTED`

## Verdict

Минимальная устойчивая boundary — не `fragments -> COMPOSE`.

```text
complete validated Declaration Model
+ one exact full-target Projection Definition
        ↓
PROJECT
        ↓
complete target document tree
        ↓
target serializer + target conformance validator
        ↓
sealed validated declaration representation
```

Рекомендация: **KEEP FIVE PRIMITIVES**.

Whole-document construction остаётся разновидностью PROJECT. Самостоятельная
COMPOSE semantics и шестая capability family не доказаны. Appendix 8 и Section
2 fragments — полезные bounded proof/debug projections, но не production
building blocks полного документа.

Exact `project_validated_declaration_fragment_v1` нельзя молча растянуть до
полного документа: он честно ограничен fragment output, одним-двумя nodes,
direct-child hierarchy и cardinality `1..1`. Будущий full-document slice
потребует новой версии PROJECT input/output contract и projection package, но
не нового фундаментального действия.

## Competing hypotheses

| Hypothesis | Supporting evidence | Contradicting evidence | Discriminating test | Verdict | Complexity |
| --- | --- | --- | --- | --- | --- |
| H1: COMPOSE — шестой primitive | два independently proven fragment; G5.24 candidate назвал `missing_runtime_capability` | official format задаёт один ordered document model; fragments не являются complete subdocuments; merge должен был бы изобрести header, taxpayer, signer, tax totals и missing tax-payment semantics | current fragments, вложенные в skeleton, не проходят XSD; bare fragment collection не имеет global declaration; между Appendix 8 и Section 2 нет XSD key/keyref/merge identity | `FALSIFIED` | high: новый primitive, fragment-list contract, duplicate hierarchy/order/validation ownership |
| H2: full declaration остаётся PROJECT | действие по-прежнему отображает complete source semantics в конкретный target; один in-memory full tree проходит XSD structure; та же модель естественно допускает XML и отдельную PDF projection | current PROJECT v1 contract специально fragment-only и не принимает complete model | static v1 contract comparison + direct full-tree XSD experiment | `SURVIVES WITH VERSIONED CONTRACT` | low/medium: один новый projection version, без новой family |
| H3: fragment-first — research scar | Section 2 proof не содержит обязательный `РасчНалПУ`; official `НДФЛ3` — одна sequence из 14 child families; current PROJECT artificially caps target at two nodes | fragments сохраняют локальную проверяемость и provenance и потому остаются полезны | bare collection/missing-node/order experiments fail; direct complete tree succeeds structurally | `SURVIVES` | lowest if fragments remain derived views rather than production inputs |
| H4: PROJECT с отдельными internal target adapters | construction, byte encoding and validation have different invariants; XML requires XSD plus embedded Schematron/file rules; PDF would require another adapter but the same source model | adapters must fail atomically and must not become user-visible pseudo-capabilities or plugins | XSD rejects missing/order errors after construction; embedded Schematron count proves XSD-only pass is not final conformance | `SURVIVES; REFINES H2/H3` | low if closed and target-versioned; high if generalized into DSL/plugin platform |

## Official full-document audit

Проверены exact bytes, опубликованные на
[странице приказа ФНС](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/):

```text
form PDF          d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565
procedure DOCX    7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc
format DOCX       f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2
XSD 5.20.01       083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484
```

[Official XSD 5.20.01](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd)
задаёт один global root `Файл`. Обязательная верхняя hierarchy:

```text
Файл
  Документ
    СвНП
    Подписант
    НДФЛ3
```

`Файл` владеет `ИдФайл`, `ВерсПрог`, `ВерсФорм`; `Документ` — `КНД`,
`ДатаДок`, `Период`, `ОтчетГод`, `КодНО`, `НомКорр`. Taxpayer identity и
signer — обязательные containers, а не свойства Appendix 8/Section 2
fragments.

Внутри `НДФЛ3` одна XSD `sequence` из 14 child families:

| Order | Element | Cardinality |
| ---: | --- | --- |
| 1 | `СумНалПу` | `1..1` |
| 2 | `ЗаявРаспДС` | `0..1` |
| 3 | `НалБаза` | `1..unbounded` |
| 4 | `ДоходИстРФ` | `0..unbounded` |
| 5 | `ДоходИстИно` | `0..1` |
| 6 | `ДоходПредпр` | `0..1` |
| 7 | `ПрофНалВыч` | `0..unbounded` |
| 8 | `ДоходОсвПрев` | `0..1` |
| 9 | `ВычСтандСоц` | `0..1` |
| 10 | `ИмущНалВычПр` | `0..1` |
| 11 | `ИмущНалВычНов` | `0..1` |
| 12 | `ДохОперЦБ` | `0..unbounded` |
| 13 | `ДохПродОНИ` | `0..1` |
| 14 | `ВычСоцИнв219` | `0..1` |

Каждый `НалБаза` содержит оба required child:

```text
РасчНалБаза  1..1
РасчНалПУ    1..1
```

G5.24 доказал только первый child. Поэтому его Section 2 result — намеренно
partial fragment, а не самостоятельный valid `НалБаза` occurrence.

XSD содержит 72 element declarations, 24 sequences, 2 choices, 15 explicit
repeated elements и 44 explicit optional elements. В нём нет `xs:key`,
`xs:keyref` или `xs:unique`, и нет embedded Schematron assertion, одновременно
связывающего `НалБаза` с `ДохОперЦБ`. Их согласованность — upstream declaration
semantics/provenance responsibility, не merge identity.

Official format также требует XML 1.0, `windows-1251`, version `5.20`,
определённое имя файла и соответствие `ИдФайл`. В XSD embedded 15 Schematron
assertions, включая file-name и conditional-presence rules. Следовательно,
обычный XSD pass необходим, но сам по себе недостаточен для полного official
conformance.

## Disposable falsification experiment

Вне repository, только in-memory, официальный XSD был загружен как
`lxml.etree.XMLSchema`. Никакой production code или fixture не создан.

| Input | XSD result | What it discriminates |
| --- | --- | --- |
| complete ordered skeleton с research-only placeholder tax-payment values | `PASS` | единый direct projection способен построить structural full tree; COMPOSE не требуется для самой hierarchy |
| тот же tree без `РасчНалПУ` | `FAIL`: expected `РасчНалПУ` | два current fragments недостаточны |
| тот же tree без `СумНалПу` | `FAIL`: expected `СумНалПу` | merge не может ограничиться Appendix 8 + bounded Section 2 |
| те же nodes, но `ДохОперЦБ` перед `НалБаза` | `FAIL`: wrong sequence | order принадлежит target projection/schema, не caller merge |
| bare `НДФЛ3` collection из двух current fragments | `FAIL`: no global declaration | fragment list не является official document contract |

Первый `PASS` — только structural experiment. Placeholder zeros не являются
налоговой истиной, embedded Schematron не исполнялся, taxpayer completeness не
доказана. Этот тест нельзя использовать как декларацию или расчет.

## Why COMPOSE is not a stable semantic

Строго рассмотренные candidate responsibilities распределяются без нового
primitive:

| Proposed COMPOSE responsibility | Actual owner |
| --- | --- |
| resolve full hierarchy | full-target Projection Definition + official XSD |
| place/order nodes | deterministic target document builder inside PROJECT |
| choose/repeat occurrences | typed Declaration Model collections + projection mapping |
| fill metadata | Declaration Model/context semantics, mapped by PROJECT |
| deduplicate | upstream model identity/completeness; PROJECT must reject ambiguity, not reconcile |
| bind Appendix 8 and Section 2 | common source Declaration Model/provenance, not fragment matching |
| serialize XML | closed XML target adapter |
| enforce XSD/Schematron | target conformance validator |
| calculate missing `РасчНалПУ`/totals | future Tax/Declaration semantics owner; forbidden in projection |

После такого ownership split у COMPOSE не остаётся самостоятельной business
semantics. Он становится либо другим названием PROJECT, либо небезопасным
fragment merge, либо техническим XML builder/validator.

Pressure test на другую декларацию также отрицателен для COMPOSE: не каждая
форма естественно представляется набором независимо опубликованных fragments.
Действие `complete semantics -> target representation` остаётся осмысленным.

## Surviving boundary contracts

### Input: complete validated Declaration Model

Непосредственный input final PROJECT — не Financial Case, не raw Tax Models и
не fragment list. Это versioned Declaration Model, который содержит:

- exact declaration identity, period and correction context;
- taxpayer, tax authority and signer semantics;
- complete typed collection of applicable tax/declaration semantic
  occurrences;
- document-level tax/payment/refund semantics, включая необходимые
  `РасчНалПУ` и `СумНалПу` meanings;
- explicit applicable/absent distinction for optional sections;
- completeness binding to exact source Tax Models and context evidence;
- provenance without target paths/codes.

Этот model не пересчитывает Tax Models и не владеет XML ordering.

### Projection Definition

One exact published target package owns:

- jurisdiction/form/target/version;
- exact official format, XSD and rule-set hashes;
- mappings from named Declaration Model concepts to target fields/codes;
- form-specific presence/cardinality/order binding;
- allowed closed formatting transforms;
- serializer/validator conformance identity.

Official XSD remains structural evidence/validator authority. Projection JSON
must remain mapping data: no XPath mutation, conditions DSL, loops,
expressions, workflow graph or arbitrary template language. Choice should come
from typed union semantics; repetition from typed collections; optional output
from explicit presence, not executable expressions.

### Immediate pre-serialization object

PROJECT constructs one complete ordered target document tree. It is sealed by:

- projection/package identity and hashes;
- exact Declaration Model hash;
- source-concept to target-node provenance/accounting;
- deterministic node/cardinality/order inventory.

This target tree is the object immediately before XML serialization. It is not
a stable cross-representation Declaration Model and must not flow back into
tax calculation.

### Final representation

For XML, a closed target adapter serializes exact encoding/namespace/order and
then validates XSD plus the applicable official Schematron/extension rules.
The PROJECT result may expose sealed bytes/hash and a validation receipt, but
validation failure returns no publishable representation.

Construction, serialization and validation should be separate code owners and
test surfaces. They remain internal conformance stages of one PROJECT action,
not three runtime capability families.

## XML/PDF pressure test

```text
Declaration Model
  ├─ XML Projection Definition -> XML tree/bytes -> XML validator
  └─ PDF Projection Definition -> form/render target -> PDF/form validator
```

The Declaration Model and PROJECT action survive. Target tree, serializer,
field mappings and validator change. This is simpler and more honest than
making XML fragments the stable source for a future PDF.

G5.25 does not prove that an official PDF target has sufficient machine
constraints; PDF is only an architecture pressure test here.

## Authoring/compiler finding

G5.24 candidate placed two projection artifacts in one PROJECT composition,
although runtime accepts exactly one `projection_ref` per invocation. The
compiler currently:

1. resolves every listed artifact;
2. verifies that each artifact advertises the capability role;
3. does not enforce capability-specific artifact cardinality or one
   invocation's compatible input/output pair.

Immediate classification: **local validation omission plus a limited bag-like
composition representation**. It is not evidence for COMPOSE.

The minimal future correction is to require exactly one compatible projection
artifact for one PROJECT composition. A full declaration should reference one
full-target projection artifact. Multiple bounded previews remain separate
requirements/invocations. No workflow/dataflow DSL is justified by this bug.

Declaration Definition authoring remains semantic: the LLM names declaration
requirements and published identities. It must not author XML tree mutation,
node order, XPath, loops, serializer code or fragment merge algorithms.

## Ownership / hardcode pressure test

| Question | Owner |
| --- | --- |
| Где tax meaning и calculation? | Tax Methodology / reviewed behavior |
| Где stable calculated values? | Tax Models and complete Declaration Model references |
| Где структура конкретной формы? | exact official XSD/format inside SHA-pinned target package |
| Где form-version field/code mapping? | versioned Projection Definition |
| Где document hierarchy/order/cardinality? | official structural contract + deterministic PROJECT builder |
| Где serialization? | closed target-specific adapter |
| Где validation? | input owner first; then projection validator; finally target XSD/Schematron conformance validator |
| Что меняется при новой версии ФНС? | target package/ref, mappings and target adapter conformance; PROJECT family stays |
| Что остаётся стабильным? | Tax Model meanings unless tax law changes, Declaration Model concepts where compatible, PROJECT action and provenance law |
| Где lifecycle/authoring UI? | existing repository publication and, if later needed, existing OpenWebUI authoring surfaces; not runtime projection |

No Projection DB, registry service, ACL, workflow, GUI or new ArtifactStore is
required by this boundary.

## Rejected models

### Sixth COMPOSE primitive

Rejected: its alleged responsibilities already belong to source completeness,
target projection, serialization or validation. Current fragments do not form
a complete or self-identifying document algebra.

### Fragment list as production input

Rejected: it duplicates hierarchy, permits incompatible artifact sets, loses a
single completeness owner and does not generalize to PDF. Fragments remain
derived evidence/views.

### XML tree as stable Declaration Model

Rejected: it moves form-version paths/codes/order upstream, couples Tax Model
semantics to XML and blocks clean alternative target projections.

### Generic XML/template DSL

Rejected: official structure, typed source model, closed mappings and standard
validators provide the required behavior without arbitrary executable rules.

## Unresolved questions for a separately authorized implementation goal

1. Exact minimal Declaration Model contract and its completeness owner are not
   yet published.
2. Required tax/payment semantics for `РасчНалПУ` and `СумНалПу` are absent
   from the current bounded scenario; projection must not invent them.
3. The exact FNS Schematron/`usch` execution environment and validation receipt
   contract require a targeted tooling proof beyond XSD-only validation.
4. Applicability/completeness rules for all 14 child families are not proven.
5. Exact full-target projection artifact shape and a non-DSL authoring
   validator remain to be designed.
6. PDF/form-filling constraints were not audited and remain a pressure test,
   not a supported target.

These are implementation/evidence gaps inside the surviving boundary, not
evidence for a sixth primitive.

## KISS decision

The surviving model has:

```text
one complete semantic input
one target projection package
one PROJECT action family
one target tree
closed serializer and validator adapters
zero fragment merge contracts
zero new base primitives
```

It minimizes owners, intermediate representations, duplicated target data and
declaration-specific runtime control flow while keeping construction and
validation independently testable.

## Scope stop

G5.25 is research-only and closed. No runtime, capability contract, compiler,
Declaration Model, full projection artifact, XML generator, XSD/Schematron
pipeline, PDF, filing, GUI, workflow, Tax Model or methodology was implemented.

The next implementation slice, if separately authorized, should begin with the
minimal complete Declaration Model/input-completeness contract and only then a
versioned full-target PROJECT proof. It must not begin with fragment COMPOSE.
