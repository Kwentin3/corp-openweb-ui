# Broker Reports — Gate 3 Minimal Fail-Closed Granularity G5.83

Дата: 2026-08-17
Статус: `G5_83_CONTRACT_PROVEN_ORDINARY_REPLAY_FAIL_CLOSED`
Рабочая ветка: `feature/gate5-tax-period-category-aggregation`

## Итог

Минимальная unsafe unit для всех пяти source-qualified инцидентов G5.80 —
отдельный role binding. Строгий validator по-прежнему отклоняет неверную
привязку; отклонённые target/literal не попадают в sidecar. Существующий
`FinancialAnnotationsV2` уже выражает результат как `status=missing`, а
существующий Gate 4 — как `role_incomplete`. Новая schema, state machine или
partial-publication framework не потребовались.

Детерминированный replay исходных exact outputs доказал локальную семантику на
пяти инцидентах, затем на всех 140 chunks. Provider calls на этом этапе: `0`.

## Source qualification пяти инцидентов

Original PDF использовался только для diagnosis. Пять страниц были визуально
проверены в private evidence; значения, изображения и customer bytes в Git не
переносились. Сопоставление выполнено по цепочке original PDF → Canonical →
pass-1 fact proposal → pass-2 roles → validator.

| Chunk | PDF page | Facts | Rejected role bindings | Affected facts | Other independent facts | Minimal unsafe unit |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 10 | 4 | 45 | 4 | 2 | 43 | role |
| 12 | 5 | 45 | 26 | 13 | 32 | role |
| 42 | 20 | 35 | 1 | 1 | 34 | role |
| 44 | 21 | 35 | 1 | 1 | 34 | role |
| 76 | 35 | 13 | 1 | 1 | 12 | role |
| **Total** | — | **173** | **33** | **18** | **155** | **role** |

Ранее сохранённый batch показывал только первый validator error каждого
chunk. Полное детерминированное прохождение всех role bindings выявило 33
неверные привязки в 18 facts. Каждый соответствующий fact identity и его
atomic source target оставались доказанными; недоказан был только конкретный
role source binding. Зависимости, требующей подавить соседние facts или chunks,
не обнаружено.

## Safety и KISS

Реализована узкая локализация только для source-binding ошибок уже структурно
валидной роли:

- unknown target alias;
- target вне accepted fact context;
- empty/non-literal `exact_text`;
- ambiguous composite target.

Такая роль сохраняется только как `missing`; ошибочный target и literal
отбрасываются. Если роль required, fact остаётся `role_incomplete`. Optional
role rejection не делает fact неполным, но остаётся в rejection accounting.

Структурные и identity ошибки — несовпадение fact set/label, неизвестная роль,
неверная cardinality, malformed response или отсутствующий canonical target —
по-прежнему отклоняют весь proposal/chunk. Для более мелкой локализации этих
ошибок понадобился бы новый partial-response protocol; G5.83 его не строит.

`document_status` теперь отвечает только на вопрос, получил ли каждый chunk
contract-valid output. Отдельный `source_fact_completeness_status` остаётся
`incomplete`, если required roles отсутствуют. Поэтому `complete` не
интерпретируется как полнота или истинность financial facts.

## Реализация

- `Gate3RoleLabelingFactory.create_from_chunk` остаётся единственным owner
  pass-2 validation и локально переводит только допустимые source-binding
  rejections в explicit `missing`.
- `Gate3ChunkBatchLabelingFactory.create` сохраняет contract-valid chunks с
  локальными отказами и считает отдельно unusable chunks, incomplete facts и
  rejected bindings.
- `Gate3FinancialAnnotationsPersistenceFactory.create` остаётся единственным
  persistence owner; перед immutable save он проверяет согласованность новых
  aggregate metrics.
- `Gate4FinancialCaseRuntimeFactory.create` и существующий `role_incomplete`
  status использованы без новой модели исходов.
- Generated OpenWebUI bundles перестроены штатным builder.

G5.83 не менял Gate 2 owner/source/contracts, runtime imports, dependency
manifest, Role Pack, prompt/model config, decimal normalization, methodology,
metadata/VLM или user/case route. Штатный all-target bundle builder механически
обновил уже dirty generated projections, включая Gate 2 bundles; семантических
Gate 2 правок в рамках G5.83 не вносилось. Retry, repair, fallback, best-of-N,
verifier, manual facts и новые relations не добавлялись.

## Deterministic exact-output proof

Frozen batch SHA-256:
`c3b3d8eacd28e721befe88e671c57d604e59e49e37d3801b5a8ae27a8204c045`.

| Metric | Exact five | Full 140 chunks |
| --- | ---: | ---: |
| chunks validated | 5/5 | 140/140 |
| chunks with local failures | 5 | 5 |
| fully unusable chunks | 0 | 0 |
| annotations/facts retained | 173 | 1489 |
| role-complete facts | 154 | 1263 |
| role-incomplete facts | 19 | 226 |
| facts incomplete due to rejection | 18 | 18 |
| rejected facts | 0 | 0 |
| rejected role bindings | 33 | 33 |
| provider calls | 0 | 0 |

В exact-five выборке есть 19 role-incomplete facts: 18 стали incomplete из-за
source-qualified rejection, ещё один имел ранее явный model `missing` и не был
искусственно дополнен. Full result имеет `document_status=complete` и отдельно
`source_fact_completeness_status=incomplete`.

Sidecar успешно сохранён штатным persistence owner. Детерминированный Gate 4
rebuild дал:

```text
status                    CASE_COMPLETE_FOR_CURRENT_INPUT_SET
sources total             4
facts total               1783
role-complete facts       1553
role-incomplete facts      230
invented relations           0
```

Разница между 1489 facts текущего документа и 1783 facts case inventory — 294
facts трёх других readiness-visible документов. Внутри текущего документа
G5.80 сохранял 1316 facts из 135 принятых chunks. Новые 1489 дают ровно `+173`
facts — полный fact inventory пяти ранее целиком подавленных chunks. Из этих
173 только 18 required-role facts остаются incomplete из-за 33 локальных
rejections; остальные 155 independently validated facts сохранены. Rejected
bindings не превращались в значения. Duplicate `fact_id`: `0` (case rebuild
fail-closed отклоняет duplicate identity). Stored relations: `0`; похожие
source facts разных документов не склеиваются и не получают связь.

Safe deterministic receipt:
`BROKER_REPORTS_GATE3_MINIMAL_FAIL_CLOSED_G5_83.deterministic.safe.json`.
Private result SHA-256:
`ddc49ccf3eebadfb8c447f07b2d3bb82375147b6c9ea2ef38485c964f0258d5c`.

## Ordinary provider replay

После deterministic proof и contract update выполнен ровно один ordinary
replay через current production Gate 3 model/config. Все 188 started submissions
вернулись. Retry/repair/best-of-N/model change/prompt tuning: `0`.

| Metric | Ordinary result |
| --- | ---: |
| chunks validated | 138/140 |
| chunks with local failures | 4 |
| fully unusable chunks | 2 |
| annotations retained in memory | 1421 |
| role-complete facts | 1181 |
| role-incomplete facts | 240 |
| facts incomplete due to local rejection | 4 |
| locally rejected role bindings | 4 |
| structurally rejected facts | 26 |
| provider submissions returned | 188/188 |

Четыре `gate3_role_exact_text_not_literal_substring` на chunks 12, 42, 98 и
104 были локализованы: каждый chunk получил
`validated_with_local_rejections`, неверный literal не сохранился, остальные
facts сохранились.

Два независимых terminal blockers не относятся к локализуемому role source
binding:

- chunk 24: terminal `gate2_model_provider_unavailable` во время role pass;
  pass 1 успел доказать 32 proposals, но role output отсутствует;
- chunk 106: structural `gate3_role_fact_set_mismatch`; 26 pass-1 facts не
  имеют contract-valid полного role proposal.

Итог ordinary run: `DOWNSTREAM_REPLAY_INCOMPLETE`. Это корректный fail-closed:
138 contract-valid chunks и 1421 annotations не уничтожены в in-memory
accounting, но два fully unusable chunks не позволяют публиковать полный
sidecar. Sidecar не сохранён, Gate 4 для ordinary result не перестраивался,
повторная попытка не выполнялась. Поэтому stochastic result не даёт разрешения
возобновить downstream E2E.

Исходный reused harness сохраняет исторический receipt schema/goal G5.80;
поверх него записан privacy-safe G5.83 aggregate receipt
`BROKER_REPORTS_GATE3_MINIMAL_FAIL_CLOSED_G5_83.ordinary.g583.safe.json`.

## Verification

- focused Gate 3 tests: `59 passed`;
- post-bundle Gate 3/Gate 4/architecture/Gate 1 selection: `139 passed`;
- expanded Gate 3/Gate 4/architecture/bundle selection: `148 passed`,
  `1 failed`;
- единственный failure — существующий Gate 2 closed-world bundle assertion о
  `gate2_financial_evidence_production_runtime`; он вне G5.83 и не исправлялся;
- Python compile и Ruff для изменённых source/script/tests: passed;
- deterministic exact-five replay предшествовал full replay и provider replay;
- provider retry/repair/best-of-N: `0`;
- production visual dependency: `0`.

## Privacy и repository state

Exact requests/responses, original PDF, renders, provider progress и sidecar
остаются под `.codex/private-evidence`. Git содержит только агрегаты, hashes и
safe receipts. Dirty tree помечен `PRESERVE_USER_OWNED`: clean/reset/stage/commit
не выполнялись.

## Terminal

Доказаны:

```text
GATE3_ROLE_REJECTIONS_SOURCE_QUALIFIED
MINIMAL_FAIL_CLOSED_UNIT_PROVEN
VALIDATOR_STRICTNESS_PRESERVED
LOCAL_INVALID_FACTS_FAIL_CLOSED
INDEPENDENT_VALID_FACTS_PRESERVED
WHOLE_DOCUMENT_SUPPRESSION_REMOVED_WHERE_UNJUSTIFIED
DETERMINISTIC_GATE3_DOCUMENT_ARTIFACT_CONTRACT_VALID
DETERMINISTIC_GATE4_CURRENT_CASE_REBUILT
DETERMINISTIC_CURRENT_CASE_SOURCE_FACTS_REQUALIFIED
ORDINARY_REPLAY_FAIL_CLOSED
```

Не заявляются:

```text
GATE3_DOCUMENT_ARTIFACT_CONTRACT_VALID   # ordinary run
GATE4_CURRENT_CASE_REBUILT               # ordinary run
READY_TO_RESUME_DOWNSTREAM_E2E
```

Текущий terminal ordinary run: `DOWNSTREAM_REPLAY_INCOMPLETE`. Новый replay
или downstream GOAL требует отдельной авторизации.
