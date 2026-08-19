# Broker Reports Gate 5 Semantic Obligation Coverage Research — G5.28A

Date: `2026-08-10`

Status: `G5.28A_CLOSED`

Recommendation: `SEMANTIC_OBLIGATION_ACCOUNTING_REQUIRED`

Corrected G5.28 trial: `NOT_RUN`

G5.29 / product runtime: `NOT_STARTED / NOT_ALLOWED`

## Verdict

Минимальный механизм — небольшой hash-pinned список **semantic obligations**,
который живёт только в authoring/publication evidence. Каждая obligation
фиксирует самостоятельный target-independent смысл, его закрытую applicability
policy и ссылки на официальное evidence. Independent LLM не придумывает и не
повторяет эти смыслы: она группирует их по exact `obligation_id` в небольшой
domain manifest.

Deterministic validator не знает правильного списка domains. Он доказывает
другое:

1. каждая reviewed obligation использована ровно один раз;
2. в domain нет obligations с разными applicability/evidence policies;
3. domain meaning, policy и official refs собраны из referenced obligations, а
   не приняты из свободного пересказа модели;
4. typed component inventory остаётся exact или честно `missing`;
5. target layout и executable/runtime semantics отсутствуют.

Одно правило granularity:

> Official meanings можно держать вместе, пока для них достаточно одной
> applicability decision, одной закрытой evidence policy и одной связной
> aggregate component-completeness boundary; иначе authoring evidence нужно
> разделить на самостоятельные obligations.

Это сохраняет domain-level Declaration Definition. Obligation layer не
становится runtime model, tax ontology, graph или rules DSL.

## Почему surface accounting недостаточен

G5.28 дал два разных manifests, которые текущий validator считает одинаково
приемлемыми:

| Candidate | Domains | `official_surface_07` owners | Semantic result | Structural result |
| --- | ---: | ---: | --- | --- |
| frozen G5.28 | 12 | 1 | elective professional-deduction meaning потерян | `eligible_for_review` |
| disposable split variant | 13 | 2 | activity и deduction meanings представлены раздельно | `eligible_for_review` |

Exact hashes:

```text
G5.28 candidate       3a5cf39a0a70b308c72e8f8688c6785618746a4634d2c41360d6ee5f871db639
disposable split      e0962b1557ed733625c5c60dcf1817c71cd13416e26c295b63f9a9e455d5e84a
validator discriminates: false
```

Следовательно, `surface ref present` не доказывает, что сохранены все
самостоятельные meanings внутри surface. Более сильная инструкция может
снизить вероятность ошибки, но не даёт deterministic publication proof.

Официальная граница перепроверена по [приказу ФНС России от 20.10.2025
№ ЕД-7-11/913@](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/) и
[текущей странице формы 3-НДФЛ](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/).
Live DOCX порядка заполнения совпал с frozen evidence:

```text
bytes   106008
SHA-256 7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc
```

Пункт 18 действительно содержит как income/activity semantics, так и
professional-deduction semantics, включая гражданско-правовые договоры и
авторские вознаграждения. Это не post-hoc придуманный split вокруг имени
ошибочного domain.

## Competing Hypothesis Matrix

| Hypothesis | Support | Counter-evidence | Cheapest discriminating test | Observed result | Verdict | Complexity |
| --- | --- | --- | --- | --- | --- | --- |
| H1. Surface accounting + stronger prompt sufficient | G5.28 сохранил 14/14 surface refs и почти весь смысл | Один ref скрыл две независимые policies; validator принял и дефектный, и split variant | Сравнить frozen candidate с semantic split при том же surface coverage | Оба `eligible_for_review`; proof не различает их | `FALSIFIED_AS_PROOF_MECHANISM` | low, но unsafe |
| H2. Нужны semantic obligation units | Exact refs позволяют доказать отсутствие потери независимо от domain partition | Слишком мелкие units могут стать paragraph/field mirror | Проверить decision-significant units на пяти разных surfaces | Маленького набора достаточно; sentence atoms не нужны | `SURVIVES_WITH_BOUNDED_GRANULARITY` | low-medium |
| H3. Split только при различии applicability/evidence owner | Точно объясняет Appendix 3 и не требует taxonomy | Одинаковая policy ещё не гарантирует coherent aggregate component | Проверить mandatory, elective, occurrence, mixed и aggregate cases | Различие policy детерминированно требует split; component coherence остаётся review | `SURVIVES_AS_PRIMARY_SPLIT_RULE` | low |
| H4. Post-hoc deterministic audit выводит obligations из raw evidence | Не добавляет pre-authoring evidence layer | Без заранее закодированной ontology такой audit должен сам понимать налоговый текст | Попытаться сформулировать closed checks без obligation refs | Получается либо hardcode/ontology, либо ещё один nondeterministic LLM review | `FALSIFIED_AS_SOLE_VALIDATOR` | high |
| H5. Reference-preserving obligation accounting | Coverage сводится к exact set accounting; model свободно выбирает domains | Нужна небольшая reviewed preparation boundary | Прототип exact-once + same-policy validation | Good partition pass; loss и mixed-policy fail | `SURVIVES_AND_PREFERRED` | low-medium |
| H6. Model сама перечисляет покрытые submeanings | Не нужен отдельный package | Candidate одновременно claim и proof; пропущенный смысл не заявит о своём отсутствии | Удалить meaning из self-declared списка | Validator не узнаёт о потере | `FALSIFIED_CIRCULAR` | low, unsafe |
| H7. Validator знает expected domain partition | Полностью детерминирован | Уничтожает independent authoring и подменяет результат answer key | Дать expected IDs/count/splits | Trial становится проверкой воспроизведения taxonomy | `FALSIFIED_BY_INDEPENDENCE_CONTRACT` | medium, biased |
| H8. Sentence/paragraph/XSD atoms + graph | Формально высокая traceability | Создаёт form mirror, persistent ontology и дорогую change surface | Сравнить необходимые поля/relations с exact-reference ledger | Relations, field atoms и target nodes не нужны для известных failures | `FALSIFIED_BY_KISS_AND_TARGET_INDEPENDENCE` | very high |
| H9. Второй LLM/critic или consensus | Полезен для semantic review | Не deterministic; модели могут разделять один blind spot | Поменять critic outcome при неизменных exact bytes | Не даёт fail-closed proof | `SUPPLEMENTARY_REVIEW_ONLY` | medium |

## Discriminating cases

| Case | Official meanings | Applicability/evidence pressure | Typed component pressure | Decision |
| --- | --- | --- | --- | --- |
| coherent occurrence | domestic taxable income + source/kind/tax-agent facts | одна `factual_occurrence` decision | значения одной source-income family | одна obligation |
| multiple meanings, same mandatory decision | filing instance + taxpayer identity/status + signer authorization | всё `definition_mandatory` | subcomponents могут различаться, но независимо не выключаются | root aggregate допустим |
| mixed applicability | professional activity classification + civil/author deduction claim | `typed_legal_classification` против `elective_claim` | разные decision owners и разные scope outcomes | две obligations |
| elective aggregate | standard/social/investment/savings claims + calculation detail | одна `elective_claim` boundary | один deduction aggregate с внутренними variants | root aggregate допустим |
| mandatory aggregate | income-group base + tax settlement | одна `definition_mandatory` boundary | один bounded non-empty group aggregate | одна obligation |

Тест показывает две разные оси:

- несовместимые applicability/evidence policies всегда требуют split;
- разные внутренние component owners сами по себе split не требуют, если один
  root decision и один coherent aggregate сохраняют variant/completeness
  boundary.

Поэтому правило `one domain = one component` отвергнуто. Component coherence —
вторичная publication-review проверка, а не новая связь в obligation schema.

## Obligation и domain — разные уровни

```text
reviewed official evidence
        ↓
small semantic-obligation evidence package
        ↓ exact obligation refs
independent LLM grouping
        ↓
small semantic-domain manifest
        ↓
deterministic accounting + publication review
```

`obligation` отвечает на вопрос: «какой самостоятельный официальный смысл
нельзя потерять и какой тип решения открывает/закрывает его scope?»

`domain` отвечает на вопрос: «какие совместимые obligations удобно собрать в
один стабильный root owner?»

Полнота obligations детерминирована exact-reference accounting. Оптимальность
domain grouping полностью детерминировать без собственной semantic ontology
нельзя и не нужно. Она ограничивается закрытыми policy-инвариантами и коротким
publication review.

## Minimal Evidence Representation

Минимальная запись содержит только четыре поля:

```json
{
  "obligation_id": "stable-target-independent-id",
  "semantic_requirement": "reviewed target-independent meaning",
  "applicability_policy_id": "closed-policy-id",
  "official_evidence_refs": ["exact-official-evidence-ref"]
}
```

Граница хранения:

- hash-pinned, reviewed authoring/publication evidence;
- не runtime artifact и не часть case-time Declaration Model;
- без relationships, dependency edges, формул, условий и workflow;
- без PDF/XML/XSD coordinates в semantic identity;
- official locators остаются только в evidence refs;
- новая obligation появляется лишь когда потеря meaning меняет самостоятельную
  applicability/evidence decision либо completeness owner package.

`semantic_requirement` здесь не новый tax DSL. Это короткая reviewed формулировка
того, что уже требует официальный источник. Legal extraction в этот маленький
evidence package остаётся явной review boundary; validator не притворяется, что
механически доказал полноту чтения законодательства.

## Deterministic Validation Strategy

Validator получает reviewed obligation package и candidate grouping, но не
expected domains, IDs, count или partition.

Fail-closed алгоритм:

1. Проверить hash/schema/closed IDs authoring package.
2. Потребовать, чтобы каждый trusted `obligation_id` встретился в candidate
   ровно один раз.
3. Отклонить unknown, duplicate, uncovered refs и пустые domains.
4. Для каждого domain потребовать одну identical closed
   `applicability_policy_id` у всех members.
5. Скомпилировать domain semantic meanings, policy и union official refs из
   obligations. Не доверять повторению этих значений моделью.
6. Потребовать, чтобы каждый official surface был подкреплён хотя бы одной
   obligation, а каждая obligation — exact official evidence.
7. Проверить expected component как exact current inventory refs либо честный
   gap; `published_exact` не выводить из близкого по смыслу bounded contract.
8. Отклонить target layout, executable rules, fact paths, runtime workflow и
   case-time reasoning.

Disposable prototype над шестью obligations дал терминальные результаты:

```text
good partition                  PASS
lost obligation                FAIL uncovered obligation ref
mixed activity+deduction       FAIL mixed policy domain
graph edges                    0
form/XML field atoms           0
runtime artifact               false
```

Это именно coverage proof, а не proof правильности всей налоговой
интерпретации.

## Остаточный publication review

После deterministic pass человеку остаются три bounded вопроса:

1. Образуют ли same-policy obligations один понятный applicability question?
2. Существует ли для aggregate один coherent typed component family с честной
   completeness boundary?
3. Полностью ли reviewed obligation package передал самостоятельные meanings
   официального evidence?

Третий вопрос является trust boundary подготовки evidence. Устранить его без
generic legal ontology или case-time LLM reasoning нельзя. Это не причина
менять domain-level архитектуру: candidate больше не может молча потерять уже
reviewed obligation, а review остаётся малым и auditable.

## KISS / anti-ontology audit

Surviving design добавляет:

```text
1 authoring-only record kind
4 fields
exact set accounting
1 same-policy invariant
```

Он не добавляет:

- sentence/paragraph/field taxonomy;
- relationship/dependency graph;
- generic legislation parser;
- alternate tax rules language;
- runtime resolver или case-time LLM;
- expected domain answer key;
- форму/XSD как semantic model.

При равной semantic safety это меньше persistent concepts, validator logic и
future maintenance, чем любой surviving alternative.

## Change pressure

Если ФНС перепишет один paragraph, объединяя или разделяя два смысла:

1. обновляются exact official bytes/refs и hash;
2. reviewer изменяет только затронутые obligation records;
3. independent authoring и deterministic validation повторяются;
4. Definition candidate меняется только если новая группировка это требует.

Runtime code, ontology graph и rules engine не меняются. Отдельная будущая
работа над typed component возможна только если изменился сам исполняемый
contract, но не является частью semantic coverage mechanism.

Для другой декларации применяется то же правило independent applicability
meaning + exact accounting. Универсальный parser законодательства не нужен.

## Unbiased future clean authoring trial

Новый G5.28 trial разрешён только отдельным следующим шагом после этого verdict:

1. Freeze полного reviewed obligation-evidence package и его hashes до вызова
   модели.
2. Новый пустой context; один inference; `history=0`, `retry=0`, `repair=0`.
3. Не показывать G5.28 candidate, ошибочный domain ID, G5.27 partition, prior
   domain IDs, ожидаемые split/IDs/count, validator errors или roadmap.
4. Дать модели official evidence, закрытые policy definitions, exact component
   inventory и exact obligation refs.
5. Получить только domain grouping над obligation refs и expected component
   families/contracts/gaps.
6. Freeze raw output до любой проверки; затем выполнить deterministic validator.
7. Только post-hoc сравнить с G5.28/G5.27.
8. Отдельно провести bounded publication review component coherence и
   obligation-package completeness.
9. Публиковать Definition только если все границы прошли fail closed.

В G5.28A этот trial намеренно не запускался: иначе исследование превратилось бы
в repair известного ответа.

## Scope stop and next boundary

В этом GOAL:

- production/runtime code не менялся;
- validator implementation не менялась;
- corrected G5.28 candidate не создавался и не публиковался;
- questionnaire, Scope Resolution, Tax Models, Declaration Model, tax payable,
  XML/PDF не начинались;
- commit, push и PR не выполнялись.

`G5.29` остаётся запрещён. Следующая допустимая граница — отдельная
authoring-only ревизия obligation evidence/validator, затем новый независимый
G5.28 trial без answer leakage.

Machine-readable research matrix:
[`BROKER_REPORTS_GATE5_SEMANTIC_OBLIGATION_COVERAGE_G5_28A.research.safe.json`](./BROKER_REPORTS_GATE5_SEMANTIC_OBLIGATION_COVERAGE_G5_28A.research.safe.json).
