# Broker Reports G5.41 — подготовка декларации из брокерских evidence

Дата: 2026-08-13

## Итог

```text
EVIDENCE_INTAKE_CONTRACT_PROVEN
CLIENT_EVIDENCE_REVIEW_PROVEN
DECLARATION_SCOPE_ACTIVATION_PROVEN
HUMAN_GAP_CLOSURE_LOOP_PROVEN
DECLARATION_PREPARATION_WORKFLOW_PROVEN
REAL_EVIDENCE_GAPS_REMAIN
```

На frozen real corpus доказан рабочий путь от нормализованных документов до
минимального набора точных действий клиенту и target-independent проекта
декларации. Реальный case пока не готов к декларации: обязательные evidence и
filing facts отсутствуют, поэтому XML/PDF не выпускались.

Это положительный продуктовый результат с честной fail-closed границей, а не
`REAL_DECLARATION_CASE_PROVEN`.

## G5.41A — evidence intake

В четырёх документах найдены и типизированы 15 явно подписанных metadata facts:

| Категория | Facts |
| --- | ---: |
| party/client metadata | 1 |
| broker metadata | 1 |
| account metadata | 4 |
| statement period | 8 |
| tax identifiers | 1 |

Каждый факт имеет document/canonical/node/field/source-ref provenance и hash
совпавшего фрагмента. Значения и private refs в Git не опубликованы.

Отдельно учтены 186 существующих финансовых source facts:

| Consumer category | Facts |
| --- | ---: |
| security | 48 |
| income | 38 |
| commission/detail charges | 47 |
| withheld tax | 37 |
| explicit source totals | 10 |

Для bounded набора явно распознанных metadata assertions:

```text
LOST_UPSTREAM = 0
PROVENANCE_COMPLETE = true
INVENTED_SOURCE_FACTS = 0
```

Metadata не получила налогового смысла. Broker identity/address/tax identifier
не превращались в income source или taxpayer residency.

## G5.41B — client-interest review

Проверены девять exact asset/currency coverage groups. Существующий
deterministic source-fact consumer вернул 19 точных required blockers. Они
сгруппированы в семь обязательных запросов дополнительных документов без
создания purchase-sale relations.

Найдено одно advisory finding по неполному withholding evidence. Оно не стало
hard blocker и содержит конкретную пользу: дополнительное доказательство может
подтвердить уже уплаченный налог и предотвратить завышение суммы к уплате.

Commission sanity:

```text
MODE = HYBRID
DETAIL = 47
AGGREGATE = 7
RECONCILIATION = not_performed
```

Withheld-tax sanity:

```text
MODE = HYBRID
DETAIL = 37
AGGREGATE = 3
RECONCILIATION = not_performed
```

## G5.41C — scope activation

Trusted Full Declaration Definition сохранил все 25 obligations как
официальное знание. Runtime активировал только девять требований из пяти
доменов:

- filing and party identity — 3;
- declaration budget disposition — 1;
- income-group tax results — 2;
- taxable income by source — 2;
- securities results — 1.

Шестнадцать нерелевантных требований не создают runtime noise. Digital assets,
investment partnership, property, vehicles, gifts и deductions не были
активированы. Отсутствие evidence не маркировалось как `NOT_APPLICABLE`.

## G5.41D — exact closure loop

После поиска в normalized facts, document metadata, других supplied documents
и доступных authority сформировано:

| Action class | Required | Advisory | Deferred |
| --- | ---: | ---: | ---: |
| additional document | 7 | 1 | 0 |
| authenticated user/case fact | 4 | 0 | 1 |

Уже найденное в документе имя использовано в точном confirmation request;
система не просит пользователя повторно вводить его. Deferred budget action не
задаётся до появления поддержанного tax settlement.

LLM adapter получает formal findings/actions без raw transactions. Он не имеет
права закрывать blocker, считать налог или менять methodology.

Synthetic control доказал replay:

1. missing acquisition document был направлен в обычный normalization path;
2. после появления нормализованного purchase fact deterministic replay дал одну
   FIFO calculation;
3. authenticated confirmation было нормализовано в typed user/case fact;
4. повторный replay убрал уже закрытый вопрос;
5. stale LLM reasoning не использовалось как authority.

## G5.41E — readiness и target

Real result:

```text
ACTIVE_DEMANDS = 9
RESOLVED_DEMANDS = 0
BLOCKED_DEMANDS = 9
REAL_CALCULATIONS = 0
REQUIRED_ACTIONS = 11
ADVISORY_ACTIONS = 1
DECLARATION_READY = false
```

Причина отсутствия real calculations не изменилась: frozen evidence не содержит
ни одной exact securities group с достаточными acquisition и disposal inputs.
Поэтому machine-readable draft содержит только доказанные bindings/statuses и
не содержит выдуманных declaration values.

Target owners сохранены:

```text
Gate5DeclarationSemanticInputRuntimeFactory.create
Gate5FullTargetXmlProjectionRuntimeFactory.create
```

Существующий synthetic source-to-official-XML/XSD control прошёл в broad replay.
Он доказывает target mechanics, но не называется реальной декларацией.

## Hypothesis loops

1. Явно подписанные client/broker/account/period metadata действительно
   присутствуют в canonical real corpus. Узкий consumer-driven extractor дал 15
   typed facts с полной provenance.
2. Existing source assembly уже содержит достаточные количественные blockers
   для client-interest review. Отдельный graph/risk engine не понадобился.
3. Full Definition можно применять через intent/evidence activation: 25
   официальных obligations превратились в 9 active demands без дублирования
   каталога.
4. Findings можно сгруппировать в минимальные typed actions; synthetic document
   и user-answer replay подтвердили закрытие конкретных вопросов.
5. Integrated frozen real run подтвердил полный preparation workflow и честно
   остановился перед declaration release из-за exact evidence gaps.

## Проверка

PowerShell, Python 3.11:

```text
focused G5.41: 4 passed in 3.52s
focused+broad owners/XML: 46 passed in 31.42s
all Gate 5 + Gate 4/Canonical/architecture: 479 passed in 109.86s
closed-world copied-package import: CLOSED_WORLD_IMPORT_OK
```

Первый focused run действительно исполнил четыре теста и показал две assertion
failures: draft читал currency не из канонического money value, а anti-drift
anchor не называл G5.40F factory явно. Исправлены только эти несоответствия;
повторный focused run прошёл. Первый isolated-import command не запустил Python
из-за несовместимого параметра Windows PowerShell; совместимый повтор с явной
проверкой exit code прошёл.

Safe evidence:

```text
receipt SHA-256 = 9e7f5198414f7179e6dc9787c709c0fe076a1fec42dc54438d5c76c1197c3eca
actions SHA-256 = e8135a21f540907dab4d3843a68e8b32b48e5715adc445699ad6a71072fccc66
```

## KISS и границы

- Переиспользованы Canonical Reader, Gate 4 runtime, G5.40F assembler, Full
  Definition и official target Definition.
- Canonical route: `gate3_tax_case_evidence_intake.py:151` →
  `gate5_declaration_preparation.py:69` → G5.40F factory at line 80 and official
  target Definition factory at line 94. `FACTORY_REQUIRED`/`FORBIDDEN` anchors
  присутствуют во всех пяти новых owners и проверены architecture suite.
- Добавлены пять узких владельцев A-E; универсальные ontology, rules DSL,
  workflow/risk/reconciliation engines не создавались.
- Source facts lost/invented relations/invented values: 0.
- Frozen store до/после identical; provider/LLM/retry/repair: 0.
- Private result расположен вне Git.
- Новая persistence, direct SQL, transaction graph, commit, push, PR и product
  activation не выполнялись.

## Evidence files

- Contract: `docs/stage2/contracts/BROKER_REPORTS_GATE5_DECLARATION_PREPARATION.v0.md`
- Safe receipt: `docs/reports/2026-08-13/BROKER_REPORTS_GATE5_DECLARATION_PREPARATION_G5_41.receipt.safe.json`
- Safe action matrix: `docs/reports/2026-08-13/BROKER_REPORTS_GATE5_DECLARATION_PREPARATION_G5_41.actions.safe.json`
- Exact private result: outside Git under the private-evidence boundary.
