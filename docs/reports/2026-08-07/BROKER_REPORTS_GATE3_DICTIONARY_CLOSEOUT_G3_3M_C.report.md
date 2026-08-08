# Broker Reports GOAL G3.3M-C — closeout и anti-duplication audit

Date: 2026-08-07

Status: `COMPLETED`

Runtime activation: `false`

## 1. Terminal status

```text
GOAL_G3_3M_C = COMPLETED
MEANING_OWNER_COUNT = 1
DUPLICATE_RUNTIME_MEANING = NONE
FUNCTIONAL_DUPLICATION = FOUND_AND_REMOVED
EXACT_LLM_MARKDOWN = ATTACHED_AND_AUDITED
ENGINEERING_NOISE_IN_MODEL_VIEW = FOUND_AND_REMOVED
DICTIONARY_CONTEXT_READY_FOR_G3_4 = YES
NEXT_ALLOWED_GOAL = G3.4_AFTER_HUMAN_REVIEW
```

Financial definitions и набор из девяти labels не менялись. Closeout удалил
только доказанное дублирование и model-facing metadata, не помогающую
классификации. G3.4 не начат.

## 2. Фактическая source-of-truth цепочка

```text
gate3_financial_label_dictionary.v1.json             AUTHORITATIVE
        ↓ importlib.resources + exact file SHA-256
Gate3FinancialLabelDictionary.load_published         LOADER
        ↓ validated published dictionary
Gate3FinancialLabelDictionary.render_model_markdown  RENDERER
        ↓ deterministic complete projection
model.generated.md / future one request injection    DERIVED
```

Единственное физическое место, где нормативно редактируются meaning,
positive/negative boundaries, examples и confusable cases:

[gate3_financial_label_dictionary.v1.json](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.v1.json)

```text
dictionary_id = broker-reports-financial-labels
semantic_version = 1.0.0
labels = 9
file_sha256 = 182e8d7f3604ad3d06d93c4d913df17979f21aeea669123d70c10be9d9652850
```

## 3. Definition-bearing file inventory

Normalized-whitespace scan всех 27 core fragments (`meaning`, `apply_when`,
`do_not_apply_when`) дал следующий inventory.

| File | Classification | Exact current core fragments | Почему не второй runtime owner |
| --- | --- | ---: | --- |
| `broker_reports_gate1/gate3_financial_label_dictionary.v1.json` | `AUTHORITATIVE` | 27/27 | единственное редактируемое runtime-значение |
| `docs/stage2/research/BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.model.generated.md` | `DERIVED` | 27/27 | целиком строится renderer-ом; exact parity проверяется тестом |
| этот closeout report, exact block ниже | `DERIVED` | 27/27 | обязательная читаемая evidence-копия, не загружается runtime |
| `docs/stage2/research/BROKER_REPORTS_GATE3_NDFL_LABEL_DICTIONARY_G3_3V.candidate.md` | `RESEARCH / PROVENANCE` | 17/27 | human-review кандидат, предшествующий published owner |
| `docs/stage2/research/BROKER_REPORTS_GATE3_NDFL_LABEL_DICTIONARY_G3_3R.draft.md` | `RESEARCH / PROVENANCE` | 2/27 | исторический research draft, не runtime input |
| `docs/reports/2026-08-07/BROKER_REPORTS_GATE3_NDFL_DICTIONARY_CORPUS_VALIDATION_G3_3V.report.md` | `RESEARCH / PROVENANCE` | исторические формулировки и decision matrix | объясняет происхождение решений, не загружается runtime |
| `docs/reports/2026-08-07/BROKER_REPORTS_GATE3_NDFL_MINIMAL_DICTIONARY_G3_3R.report.md` | `RESEARCH / PROVENANCE` | исторические proposed definitions | объясняет research baseline, не загружается runtime |

Остальные найденные файлы содержат только label IDs, source specimens,
contracts или acceptance evidence, но не вторую полную редактируемую копию
definitions. В runtime package core-definition fragments встречаются только в
нормативном JSON.

`DUPLICATE` после closeout: `NONE`.

## 4. Anti-duplication decision table

| Element | Что делает | Текущая requirement | Уже есть тот же механизм? | Decision |
| --- | --- | --- | --- | --- |
| JSON resource | хранит exact published definitions и approval | один нормативный meaning owner, versioned v1 | нет | `KEEP` |
| loader/renderer module | explicit load, structural validation, lifecycle и deterministic projection | один load/render path | нет; definitions в коде отсутствуют | `KEEP` |
| factory | фиксирует единственный repository-approved entrypoint | factory/authority anti-drift | не дублирует behavior, только выдаёт owner | `KEEP` |
| CLI | даёт human review команды над тем же owner | view/draft/diff/validate/approval/publish preparation | API тот же; своей financial/validation/render logic нет | `KEEP_THIN_WRAPPER` |
| generated Markdown | позволяет постановщикам прочитать exact model view и фиксирует parity | обязательное separate exact evidence G3.3M-C | runtime без него работает, но текущая evidence requirement — нет | `KEEP_AS_DERIVED_EVIDENCE` |
| contract | фиксирует ownership, lifecycle и future one-copy injection | явная boundary authority | definitions не содержит | `KEEP` |
| exact file SHA-256 | связывает version с точными package bytes и fail-closed load | immutable published version | нет после удаления semantic hash | `KEEP` |
| semantic-integrity SHA-256 | повторно хэшировал canonicalized content | отдельная текущая задача не найдена | exact file SHA полностью покрывает immutable bytes | `REMOVE_REDUNDANT` |
| hardcoded definition literals в тесте | проверяли отсутствие wording в Python module | anti-duplicate assertion | owner JSON уже содержит полный проверяемый набор | `REMOVE`; тест теперь получает wording из owner |
| approval metadata | доказывает human-approved v1 и связывает publish lifecycle | human approval boundary | file hash не доказывает approval | `KEEP` |

### Почему оставлен один hash

Exact file SHA проверяет именно bytes package resource до JSON parsing. Он
одновременно выявляет содержательные, metadata и serialization-изменения.
Удалённый semantic hash не имел независимого consumer или threat boundary: при
изменении resource вместе с code pin он не давал дополнительной защиты, а для
draft достаточно immutable `dictionary_id + semantic_version`.

До первого labeling runtime и annotation persistence ещё не существовало,
поэтому closeout смог упростить inactive v1 без миграции результатов или
создания второй версии.

## 5. Exact normative dictionary v1

Exact normative artifact приложен непосредственно как package resource:

- [gate3_financial_label_dictionary.v1.json](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.v1.json)
- bytes: `7223`
- SHA-256: `182e8d7f3604ad3d06d93c4d913df17979f21aeea669123d70c10be9d9652850`
- labels: `9`

Копия JSON в отчёте намеренно не создавалась: это стало бы ещё одним полным
definition-bearing evidence artifact без дополнительной acceptance ценности.

## 6. EXACT LLM-FRIENDLY DICTIONARY

Отдельный exact derived artifact:
[BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.model.generated.md](../../stage2/research/BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.model.generated.md).

Ниже полностью приведён exact output текущего renderer-а.

<!-- EXACT_LLM_MARKDOWN_BEGIN -->
```markdown
# Financial labels

## SECURITY_PURCHASE

Смысл: Исполненная покупка конкретной ценной бумаги для счёта.

Ставить, если:
- Источник прямо показывает исполненную покупку ценной бумаги.

Не ставить, если:
- Это transfer, position, FX, заявка или РЕПО.

Примеры:
- `Покупка`
- `Buy`
- `Purchase`

Не путать с:
- Перевод ценных бумаг
- Stock distribution

## SECURITY_DISPOSAL

Смысл: Исполненная продажа, погашение или иное возмездное выбытие ценной бумаги.

Ставить, если:
- Источник показывает sale, redemption или maturity и полученные proceeds.

Не ставить, если:
- Это transfer out, отмена, изменение позиции, РЕПО или corporate action без доказанного возмездного выбытия.

Примеры:
- `Продажа`
- `Погашение ЦБ`
- `Sell`
- `Redemption`

Не путать с:
- Перевод ценных бумаг
- Stock dividend

## DIVIDEND_INCOME

Смысл: Выплаченный или зачисленный денежный дивиденд.

Ставить, если:
- Источник прямо показывает paid или credited cash dividend.

Не ставить, если:
- Это dividend accrual, stock dividend или return of capital.

Примеры:
- `Наличный дивиденд`
- `Обыкновенный дивиденд`
- `Cash Dividend`

Не путать с:
- Начисления дивидендов
- Возврат капитала

## COUPON_INCOME

Смысл: Выплаченный или зачисленный купон по облигации.

Ставить, если:
- Источник прямо показывает payment или credit купона.

Не ставить, если:
- Это НКД сделки, погашение principal или общий interest.

Примеры:
- `Зачисление д/с (купон …)`
- `Погашение купона`
- `Coupon Payment`

Не путать с:
- НКД покупки
- НКД продажи
- Погашение ЦБ

## INTEREST_INCOME

Смысл: Фактически начисленный или зачисленный процентный доход по денежным средствам.

Ставить, если:
- Источник и направление суммы подтверждают cash-interest income.

Не ставить, если:
- Это debit interest, coupon, НКД, unpaid accrual или доход от займа ценных бумаг.

Примеры:
- `Проценты по займам "овернайт"`
- `Interest Credit`

Не путать с:
- Дебетовый процент
- Начисления процентов

## SECURITIES_LENDING_INCOME

Смысл: Фактически начисленный или зачисленный доход за передачу ценных бумаг в заём.

Ставить, если:
- Income row прямо называет securities или stock loan и содержит source value.

Не ставить, если:
- Это cash interest, margin charge, payment in lieu или общее описание договора.

Примеры:
- `Проценты по займам "овернайт ЦБ"`
- `Securities Lending Income`

Не путать с:
- Проценты по займам "овернайт" без ЦБ

## ACCRUED_COUPON_COMPONENT

Смысл: НКД как компонент расчёта покупки или продажи облигации.

Ставить, если:
- НКД или accrued coupon явно связан с transaction price, cost или proceeds.

Не ставить, если:
- Это выплаченный купон, общий accrual или informational position value.

Примеры:
- `НКД покупки`
- `НКД продажи`
- `Accrued Interest в trade row`

Не путать с:
- Погашение купона
- НКД на конец периода

## TRANSACTION_CHARGE

Смысл: Комиссия, сбор или transaction tax, прямо связанные с конкретной покупкой или продажей ценной бумаги.

Ставить, если:
- Связь с исполненной сделкой видна из той же строки или секции.

Не ставить, если:
- Это withholding, account или custody service, debit interest либо неопределённая комиссия.

Примеры:
- `Комиссионные затраты (транзактные)`
- `Комиссия Брокера`
- `Комиссия Биржи`
- `Commission/Fee в trade row`

Не путать с:
- Удерживаемый налог
- Обслуживание счета депо

## TAX_WITHHELD

Смысл: Налог, фактически удержанный из дохода.

Ставить, если:
- Withholding подтверждён income event или однозначным income section.

Не ставить, если:
- Это transaction tax, tax calculated, tax payable либо неразделённые payment и refund.

Примеры:
- `Удерживаемый налог`
- `Налог удержан`
- `Withholding Tax`

Не путать с:
- Расчет налога
- Уплата/возврат налога
```
<!-- EXACT_LLM_MARKDOWN_END -->

## 7. Human context audit

Для каждой из девяти карточек вручную проверены:

- один короткий meaning;
- одна positive boundary;
- одна negative boundary;
- только полезные source-like examples;
- ближайшие confusable cases, влияющие на выбор label.

Confusable cases не повторяют meaning: они закрывают реальные границы
transfer/distribution, sale/redemption, dividend/accrual/return of capital,
coupon/НКД/redemption, cash/securities-lending interest, trade/custody charge и
withholding/calculation/settlement.

В exact Markdown отсутствуют:

```text
hashes
version-management prose
dictionary/version identities
internal paths
receipts and approval metadata
JSON/schema/storage terminology
factory names
CI/test information
research provenance
tax methodology
```

Automated companion check подтвердил:

```text
labels=9 all_owned_fields_present=true engineering_noise=none
```

## 8. Compactness evidence

Метрики считаются по exact UTF-8 files; file bytes включают UTF-8 BOM только у
Markdown.

| Artifact | Bytes | Characters | Lines | Whitespace words |
| --- | ---: | ---: | ---: | ---: |
| normative JSON v1 | 7223 | 5667 | 187 | 544 |
| model-facing Markdown | 5634 | 3670 | 172 | 531 |

До closeout JSON занимал `7313` bytes, а model view — `5712` bytes. Удаление
дублирующего hash metadata и технического model header сократило их на `90` и
`78` bytes соответственно, не меняя ни одного financial definition.

Project-owned tokenizer для будущего G3.4 provider/model не выбран и не
используется. Установленный в окружении `tiktoken` не является dependency или
согласованным tokenizer contract этого service, поэтому ложный exact token
count не приводится.

## 9. One-context / instruction boundary

Для будущего, отдельно авторизуемого G3.4 зафиксировано правило:

```text
one model request
= one exact selected dictionary render
= exactly one injection
```

Prompt/instruction может сказать «используй только labels словаря и при
неопределённости ничего не возвращай», но не может повторять или
перефразировать definitions. Skill, Tool, Knowledge/RAG, system context и
второй renderer не должны добавлять другую копию значений.

Repository search не нашёл текущего Prompt, Skill, Knowledge/RAG или runtime
context с этими девятью definitions. G3.4 infrastructure не создавалась.

## 10. Simplification diff

```diff
- published JSON: integrity_sha256
- code: semantic hash constant/calculation/validation
- draft base identity: semantic integrity hash
+ draft base identity: dictionary_id + immutable semantic_version

- model view: dictionary_id and semantic_version header
+ model view: classification content only

- test: three hardcoded definition/example literals
+ test: complete wording inventory read from authoritative JSON
```

Никакая financial формулировка не добавлена, не удалена и не изменена.

## 11. Verification evidence

PowerShell cwd:
`services/broker-reports-gate1-proof`.

```text
python -B -m pytest -q tests/test_broker_reports_gate3_financial_label_dictionary.py
9 passed in 6.35s

python -B -m pytest -q \
  tests/test_broker_reports_gate3_financial_label_dictionary.py \
  tests/test_broker_reports_gate3_minimal_labeling_contract.py \
  tests/test_broker_reports_gate_architecture.py \
  tests/test_broker_reports_kt1_architecture_stabilization.py
66 passed, 1 warning in 45.05s

final bounded gate with projection, privacy and repository guards:
81 passed, 1 warning in 48.54s
```

Warning attribution: существующий `DeprecationWarning` в DOC6-скрипте вне
G3.3M-C. Full service suite намеренно не повторялся: его известный runner
timeout не является задачей closeout.

Test isolation использует `tmp_path`, subprocess package copy и exclusive temp
outputs. Unit under test не mocked. Irreversible boundary — добавление нового
resource + exact file-hash pin; prepared draft остаётся unloadable до этой
отдельной reviewed правки.

## 12. KISS CHECK

```text
1. Есть ли второй владелец financial meaning?
   NO. AUTHORITATIVE owner = 1.

2. Есть ли два механизма одной текущей функции?
   NO after closeout. Redundant semantic hash removed.

3. Есть ли persisted/generated artifact, без которого runtime работает так же?
   YES: generated Markdown; it remains only because exact separate human
   evidence is an explicit current acceptance requirement.

4. Есть ли защита/metadata только «на всякий случай»?
   NO after closeout.

5. Попадает ли инженерная деталь в future model view?
   NO.

6. Можно ли объяснить конструкцию одной фразой?
   YES: Есть один словарь из девяти определений. Код загружает конкретную
   версию и превращает её в короткий текст для LLM.
```

## 13. STOP

```text
GOAL_G3_3M_C = COMPLETED

MEANING_OWNER_COUNT = 1

DUPLICATE_RUNTIME_MEANING = NONE

FUNCTIONAL_DUPLICATION = FOUND_AND_REMOVED

EXACT_LLM_MARKDOWN = ATTACHED_AND_AUDITED

ENGINEERING_NOISE_IN_MODEL_VIEW = FOUND_AND_REMOVED

DICTIONARY_CONTEXT_READY_FOR_G3_4 = YES

KISS_CHECK = PASS

NEXT_ALLOWED_GOAL = G3.4_AFTER_HUMAN_REVIEW
```

Работа остановлена. G3.4 не начат.
