# Broker Reports G5.86 — Source-Local Semantic Contract & Context Precedence

Дата: 2026-08-17
Terminal: `GATE3_SEMANTIC_ROOT_CAUSE_REQUALIFICATION_REQUIRED`
Подтерминал: `LOCAL_ASSERTION_CONTEXT_CONTRACT_GAP_PROVEN`

## Outcome

G5.86 не закрыт clean terminal. Замороженный systematic class подтверждён, exact pass-1 context восстановлен для всех шести structural classes, а один focused replay выполнен. Instruction-only precedence candidate не прошёл противоположные controls и был удалён из runtime source.

Первый wrong owner уточнён:

```text
Gate3 source-local assertion packaging
```

Текущий pass-1 получает whole-table Markdown с уникальными aliases, но не получает заранее объявленный atomic assertion object. Alias однозначно восстанавливает target уже после provider proposal; он не сообщает provider до ответа: «классифицируй именно эту строку». Поэтому instruction-only закон нестабилен.

## Frozen G5.85 set

| Measure | Exact |
| --- | ---: |
| Wrong facts | 105 |
| Pages | 6: 4, 5, 6, 7, 9, 10 |
| Structural classes | 6 |
| Provider chunks | 6: 10, 12, 14, 16, 20, 22 |
| Current wrong type | `DIVIDEND_INCOME` |
| Explicit row-local tax description | 105/105 |

## Exact pass-1 context

Во всех 105 случаях доказано:

- exact G5.83 pass-1 request и chunk blob восстановлены;
- local row literal присутствует полностью;
- output target alias встречается ровно один раз и восстанавливается в canonical target;
- column/table/page context видим и структурно отделён;
- atomic assertion не объявлен до provider response: provider сам выбирает row/cell target из whole-table blob.

| Structural class | Chunk | Provider-selected target shape | First cause |
| --- | ---: | --- | --- |
| `sc_2411884a0555dbc7` | 14 | table row | B — assertion not predeclared |
| `sc_3d4a1c0266efbbe2` | 12 | date cell | B — assertion not predeclared |
| `sc_4f30a191be699a96` | 10 | date cell | B — assertion not predeclared |
| `sc_97649d53686922a3` | 10 | description cell | B — assertion not predeclared |
| `sc_e36889664a26ad71` | 16 | credit cell | B — assertion not predeclared |
| `sc_eb49e5e76a94429d` | 16 | credit cell | B — assertion not predeclared |

Это не A: local evidence не потеряно. Это не D: dictionary различает income и withheld tax. E не принимается, пока не дан явный assertion boundary contract.

## Rejected minimal candidate

Проверенный кандидат добавлял общий, не broker-specific закон:

```text
explicit local evidence dominates conflicting broader context;
broader context is used only when local evidence is absent or ambiguous
```

Ни label ids, ни document literal rules, ни parser heuristics не добавлялись. Новый schema не создавался. После focused replay кандидат отклонён и runtime instruction восстановлен до `1.0.2`.

## One clean focused pass-1 replay

| Control | Result |
| --- | ---: |
| Selected chunks validated | 6/6 |
| Semantic attempts in clean run | 6 |
| Transport submissions in clean run | 6 |
| Operational retries | 0 |
| Semantic retries | 0 |
| Role provider calls | 0 |
| Persistence writes | 0 |
| Store changed | no |
| Wrong rows no longer dividend | 26/105 |
| Wrong rows still dividend | 79/105 |
| True-dividend controls preserved | 25/25 |
| Paired existing-tax controls preserved | 86/102 |
| Paired existing-tax controls regressed | 16/102 |
| Unknown canonical targets | 0 |
| Duplicate annotation pairs | 0 |

Перед clean run один локальный process launch был принудительно остановлен оболочкой через 5 секунд до появления любого chunk outcome или semantic response. Clean replay затем выполнен один раз в новом evidence directory. Возможный незавершённый physical HTTP submission preflight не включён в счётчик clean run; semantic response/best-of-N для него отсутствует.

## Visual qualification

Исходный PDF SHA-256:

```text
7cfd297786cc91cbccbe0c2ae5bce905a2a11ac6b35e5b0a795cf9c6d41bd015
```

Глазами открыты все affected pages: 4, 5, 6, 7, 9, 10. Для каждого distinct class подтверждено:

- явное описание относится к конкретной строке;
- credit и debit rows могут иметь одинаковое tax description;
- настоящие dividend rows имеют отдельное явное local description;
- table/page context не заменяет row-local meaning.

VLM calls: 0. Production visual dependency: 0.

## Stop decisions

Из-за failed focused controls не запускались:

- второй provider replay;
- оставшийся full G5.85 semantic inventory;
- ordinary Gate 3 replay;
- Gate 4 rebuild;
- Gate 5;
- parser/VLM/methodology/decimal/metadata work.

`UNEXPLAINED SEMANTIC CLASS = 0` не заявляется. Первый оставшийся wrong fact после candidate replay локализован на annotation 63, page 5, chunk 12, class `sc_97649d53686922a3`.

## Minimal next allowed goal

Не VLM stand. Сначала нужен узкий Gate 3 slice:

```text
ASSERTION
  row_target_ref
  local_row_text

STRUCTURAL_CONTEXT
  column_headers
  table_header
  section_header
```

Нужно переиспользовать существующие row aliases и Markdown renderer, не строить generic context engine. Сначала deterministic proof, что assertion объявлен до provider call; затем один focused run с теми же controls.

## KISS / anti-drift

- runtime semantic instruction после rejected candidate не изменён;
- dictionary, Role Pack, Gate 2, parser и schemas не изменены;
- broker-specific phrase rules: 0;
- new framework: 0;
- semantic retry / best-of-N / model change: 0;
- production writes: 0;
- dirty tree сохранён как `PRESERVE_USER_OWNED`; cleanup/stage/commit не выполнялись.

## Evidence

- `BROKER_REPORTS_SOURCE_LOCAL_CONTEXT_GAP_G5_86.safe.json`
- `BROKER_REPORTS_SOURCE_LOCAL_FOCUSED_REPLAY_G5_86.safe.json`
- `BROKER_REPORTS_SOURCE_LOCAL_FOCUSED_QUALIFICATION_G5_86.safe.json`
- `BROKER_REPORTS_SOURCE_LOCAL_VISUAL_G5_86.safe.json`
- private evidence: outside Git under `broker-reports-g5.86-20260817-v1`
