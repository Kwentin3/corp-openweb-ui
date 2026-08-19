# Broker Reports Gate 5 G5.28B — Obligation-backed Trusted Full Declaration Definition

Дата proof/publication: `2026-08-10`

Статус: **PROVEN**

Trusted Definition: **REPOSITORY_PUBLISHED**

G5.29: **ALLOWED / NOT IMPLEMENTED**

Product activation, push, PR: **NOT PERFORMED**

## Итог

Независимая clean-context LLM получила не грубые form surfaces, а замороженные
reviewed semantic obligations и самостоятельно собрала небольшой
target-independent root manifest без заранее известной taxonomy.

```text
official FNS bytes
  -> 25 reviewed obligations / 14 surfaces
  -> one clean LLM call
  -> 11 root domains
  -> deterministic 25/25 exact accounting
  -> bounded aggregate-aware review
  -> trusted repository publication
```

Candidate не стал authority автоматически. Authority возник только после
отдельных hash-pinned validation и review receipts.

## Единственный owner

Сохранён существующий путь:

```text
Gate5FullDeclarationDefinitionAuthoringFactory.create
Gate5FullDeclarationDefinitionCandidateFactory.create
Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create
```

Новый registry, DB, service, reader, provider client или runtime path не
создан. Resources читаются через `importlib.resources` и проверяются по
SHA-256.

Текущий контракт:
[Full Declaration Definition v1](../../stage2/contracts/BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION.v1.md).
Предыдущий v0 сохранён как точное evidence отклонённого G5.28.

## Reviewed obligation package

```text
resource  gate5_full_declaration_obligations.ru_3ndfl_2025.v1.json
bytes     14,797
SHA-256   8065a2047b2d7bf5a1a3b87ed4dd49f65bd39e97b6a42c1acf24d2d62548b23c
status    frozen_repository_reviewed
items     25 obligations / 14 official surfaces / 4 sources
```

Каждая obligation содержит `obligation_id`, semantic requirement, один closed
policy и official evidence refs. Это authoring evidence, не Tax Model, ontology
или rules DSL.

### Official bytes replay

Все четыре источника повторно загружены 10 августа и совпали с package hashes:

| Official FNS source | Bytes | SHA-256 |
| --- | ---: | --- |
| [form PDF](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf) | 438,785 | `d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565` |
| [filling procedure DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx) | 106,008 | `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc` |
| [electronic format DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_3.docx) | 148,677 | `f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2` |
| [XSD 5.20.01](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd) | 178,427 | `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` |

## Minimal model surface

Frozen payload:

```text
resource  gate5_full_declaration_definition_authoring.primary.v1.payload.json
bytes     17,576
SHA-256   5a51aa10b3aa5e880254722f79543fefe234c189969b25d2deae8291e30bc541
bias      passed
```

Модель видела official binding, 25 obligations, closed policies, четыре
bounded component contracts, четыре локальных grouping principles и minimal
candidate contract.

Она не видела G5.27 partition, G5.28 candidate/finding, G5.28A/A.1 outputs,
expected IDs/count/partition, roadmap или downstream gap. Policy, authority
classes и evidence refs модель не повторяла: validator вывел их из obligation
refs.

## One clean inference

```text
client                  codex-cli 0.147.0-alpha.6.5
model                   gpt-5.6-sol
reasoning               high
workdir                 new empty temporary directory
sandbox                 read-only
session/history         ephemeral / 0 messages
user config/rules       ignored / ignored
provider output schema  none
provider inferences     1
transport failures      0
retry/follow-up/repair  0/0/0
best-of                 false
duration                56.029 seconds
reported tokens         7,667
exit                    0
```

Exact model output был записан напрямую как package resource и после inference
не редактировался:

```text
resource  gate5_full_declaration_definition_candidate.g528b.json
bytes     5,391
SHA-256   8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d
domains   11
```

## Deterministic validation

```text
obligations present exactly once  25/25
missing / duplicate / unknown     0 / 0 / 0
empty domains                     0
mixed policies                    0
invented contracts                0
bounded -> exact promotions       0
target-layout identities          0
executable logic                  0
validation status                 eligible_for_review
validation SHA-256                f3e4993ac54f154be53cb5d21a4ffaed0713cf49b3025b10d4e9b8b9c1bf79f6
```

Validator не содержит answer key для domain count, IDs или partition.

## Bounded semantic publication review

Review проверил только четыре ограниченных свойства:

| Check | Result |
| --- | --- |
| honest applicability question | passed |
| coherent component boundary | passed |
| obligation package completeness | passed |
| aggregate variant retention | passed |

Агрегаты `taxable_income_by_source`, `deduction_claims`,
`property_and_vehicle_dispositions` и `financial_investment_results` допустимы:
domain открывается, если применим любой релевантный member, а обязательства и
semantic meaning сохраняют внутренние варианты отдельно. Это не ложное
требование «каждое optional value — отдельный root domain».

`income_group_tax_results` и `financial_investment_results` честно ссылаются
только на `published_bounded` contracts; остальные families помечены
`missing`. Ни один bounded contract не объявлен full-domain exact.

Review receipt:

```text
resource  gate5_full_declaration_definition_review.g528b.json
SHA-256   731ae53ed77046cfd89b2aac8e53f5416c51cdb732709327a7702c2c28de1619
status    trusted_repository_published
findings  0
```

## Trusted publication

Authority разрешает только exact tuple:

```text
definition_id      ru_3ndfl_2025_root_declaration
definition_version 2026-08-10.1
definition_sha256  8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d
```

Неверный ID, version, Definition hash, validation hash, review hash или
obligation-package hash закрывает путь. Candidate factory остаётся evidence,
не authority.

## Verification

```text
focused G5.28B module          13 passed
all 18 Gate 5 test modules    166 passed
architecture suites            47 passed, 1 unrelated existing warning
```

Первый architecture run нашёл только отсутствие этого уже существующего
full-definition owner в executable new-module allowlist. После добавления
единственного owner повторный architecture run прошёл `47/47`.

Дополнительно был запущен весь service collection: `3,144` tests в `250`
files. Процесс достиг внешнего `1,804 s` timeout (`exit 124`) без pytest
terminal summary и без assertion output; оставшийся owned Python process был
проверен по command line и остановлен. Это runner limitation, не assertion
failure и не часть G5.28B acceptance. Полный релевантный Gate 5 suite имеет
terminal green result выше.

## KISS / Occam check

- один прежний owner module;
- один reviewed package resource;
- один minimal manifest;
- один deterministic validator;
- один review receipt;
- candidate bytes одновременно являются immutable published Definition;
- нет второго schema reader, registry, DB, workflow или ontology;
- runtime capability basis не изменён.

## Scope stops

Не реализованы Scope Resolver, case-time applicability, human ACQUIRE,
questionnaire, filing context, taxpayer identity resolver, missing Tax Models,
tax settlement, Declaration Model, PROJECT, XML/PDF, GUI или product route.

## Первый downstream blocker

G5.29 теперь разрешён, потому что имеет реальный trusted Definition input, но
в G5.28B не начат.

Первый case-time prerequisite — trusted filing-context binding для mandatory
domain `filing_and_party_identity`: declaration instance, taxpayer/period
status, signer и representation authority. Published Definition честно
указывает family как `missing`; существующий Financial Case не является
authority для этих filing identities.

Bounded G5.29 должен либо получить отдельно авторизованный filing context, либо
вернуть этот prerequisite как первый честный unresolved semantic blocker.
G5.28B его не исправляет.
