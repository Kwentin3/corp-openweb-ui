# Broker Reports: Hybrid PDF Context And Structural Reliability Closure

Дата: 2026-07-13

Режим: Goal 3, controlled private shadow
Итог: closure выполнен; вертикаль готова к отдельно разрешённому Gate 2 shadow E2E, production Gate 2 не изменён

## Результат

Кандидат-связанный hybrid-контур переработан так, чтобы большие таблицы обрабатывались ограниченными row-window пакетами без потери источника. Добавлены точный provider token guard, независимая проверка размещения, явная модель continuation, монотонный repeatability ledger и закрытая типизированная арбитрация.

Controlled proof на том же PDF и тех же пяти hybrid-target таблицах завершился так:

- `accepted_shadow`: 1;
- `blocked_structural_placement`: 4;
- invented model values: 0;
- потерянные при compaction/windowing кандидаты: 0 из 1,351;
- production Gate 2 selection changes: 0.

Четыре blocked результата — ожидаемый успешный fail-closed исход, а не незавершённая обработка: каждый пакет дошёл до проверяемого terminal с сохранёнными артефактами и конкретной структурной причиной. Единственная принятая tax/summary таблица сохранила точность 40/40 cells, 15/15 numeric-like и 16/16 empties.

## Корневая причина amplification

Goal 2 повторял в model-facing JSON длинные ids, source refs, word refs, bbox, checksums и заголовочные фрагменты для каждого кандидата, затем добавлял большую inline-картинку и verbose output schema. Поэтому 708 source candidates не помещались в лимит 512, а provider input достигал 73.118012x от уникального видимого текста. Локальная image-формула также недооценивала реальный Gemini input примерно в 2.33 раза.

Goal 3 отделяет private reversible ledger от минимальной model projection: dense ids, shared immutable headers, однократные word/source records и row-aligned windows. Provider получает только crop, общий column/header contract и точные candidate placement tuples.

## Compact evidence и row-window contract

`PdfHybridCompactionFactory` строит versioned private ledger. Каждый compact id обратимо разрешается в исходный private value, `source_value_ref[]`, `word_ref[]`, bbox и checksum. Fuzzy reconstruction и lossy summary отсутствуют.

`PdfHybridWindowFactory` делит только по строкам. Все окна одной таблицы имеют общий immutable column/header hash, точные упорядоченные row ranges и exactly-once ownership. Column-wise split и silent truncation запрещены. Deterministic join проверяет полное покрытие ledger до materialization.

| Table | До: candidates | После: max/window | Windows | До: model text B | После: max/window B | Actual input max |
|---|---:|---:|---:|---:|---:|---:|
| 1:3 | 241 | 150 | 2 | 27,422 | 8,795 | 7,591 |
| 3:2 | 708 | 180 | 4 | 78,573 | 9,987 | 8,995 |
| 4:1 | 343 | 135 | 3 | 38,270 | 7,745 | 7,135 |
| 4:2 | 35 | 35 | 1 | 4,779 | 3,077 | 2,949 |
| 5:3 | 24 | 24 | 1 | 3,784 | 2,673 | 2,559 |

Итого: 1,351 logical candidates, 11 primary model packages, максимум 180 candidates и 9,987 model-facing text bytes на пакет. Во всех таблицах `source_candidates_preserved == before_candidate_count`, `omitted_candidates=0`.

## Image-inclusive token calibration

Guard учитывает raster dimensions/DPI, inline image, candidate text, task, schema и ожидаемый output grid. Перед `generateContent` адаптер вызывает Gemini `models.countTokens` с тем же `generateContentRequest`, включая schema и inline image. Это соответствует официальным [CountTokens API](https://ai.google.dev/api/tokens) и [image input](https://ai.google.dev/gemini-api/docs/image-understanding) контрактам.

В финальном controlled-run выполнено 19 provider attempts:

- maximum exact provider count: 8,995 input tokens;
- maximum actual input: 8,995 tokens;
- maximum count-to-actual error: 0.0%;
- все pre-call guards: passed;
- hidden retry/failover: false.

Оценка и фактическое использование сохраняются для каждой попытки. Provider limit 1,048,576 input tokens и exact model match были подтверждены qualification; рабочий hard guard остаётся существенно ниже provider ceiling.

## Независимая structural placement проверка

Новый валидатор не использует provenance как замену геометрии. Он отдельно проверяет row order, candidate-to-row/column compatibility, grid boundaries, explicit empties, spatial overlap, repeated/merged headers и continuation coverage.

| Table | Terminal | Independent result | Основание |
|---|---|---|---|
| 1:3 | `blocked_structural_placement` | fail | candidate-column incompatibility/mismatch и empty-position mismatch |
| 3:2 | `blocked_structural_placement` | fragment pass, logical group fail | все 708 candidates размещены и repeat checksum совпал, но обязательный continuation fragment 4:1 не прошёл placement |
| 4:1 | `blocked_structural_placement` | fail | candidate-column incompatibility/mismatch и empty-position mismatch |
| 4:2 | `blocked_structural_placement` | fail | candidate-column/empty mismatch и отсутствующая merged-header relation |
| 5:3 | `accepted_shadow` | pass | complete grid, provenance, placement и required repeat совпали |

У wide table 3:2 полный placement отдельно прошёл: 708/708 candidates, четыре окна, одинаковый placement checksum `c308c208fb2a90c022034f9fd2db9dbef4ea15c2fbd3707afff58c984ddca7a8`. Она всё равно не принята как самостоятельная page-local таблица, потому что contract требует логическую continuation-группу.

## Continuation model

Continuation 3:2 + 4:1 представлена одним group id, двумя ordered fragments и общим 16-column model. Контракт фиксирует repeated-header policy, row ordering, subtotal/duplicate policy и fragment/joined coverage.

Проверено:

- fragments: 2;
- logical rows: 73 из 73;
- candidates: 1,051 из 1,051;
- word refs: 1,213 из 1,213, все уникальны;
- column boundaries: compatible;
- 150/200 DPI placement checksum 4:1: identical;
- terminal: `pdf_hybrid_continuation_fragment_placement_blocked`, потому что fragment 4:1 не прошёл независимый placement.

Это доказывает и модель объединения, и корректный запрет на принятие неполной logical continuation.

## Grouped-header repeatability

Grouped 4:2 заблокирована структурным gate до acceptance/repeat: её merged-header relation и column/empty placement не доказаны. Поэтому финальный terminal обоснован без выбора “лучшего” результата.

Repeatability gate отдельно доказан:

- accepted 5:3: identical placement checksum на обязательном повторе;
- wide fragment 3:2: identical placement checksum на обязательном повторе;
- deterministic Goal 1 control: identical materialization checksum;
- unit contract: differing same-evidence checksums устанавливают permanent `ever_conflicted`, и позднее совпадение не снимает конфликт;
- developmental controlled evidence ранее зафиксировало реальный typed `blocked_non_repeatable` для 3:2 до исправления identity/grid bugs; оно не использовано как финальный acceptance.

Retries остаются explicit и bounded; 200 DPI — отдельная evidence task, а не скрытый retry.

## Shadow arbitration

Арбитр принимает только явные сигналы deterministic, hybrid-150, hybrid-200, structure, continuation и repeat ledger. Разрешены только:

```text
accepted_shadow
human_review_required
blocked_context_budget
blocked_non_repeatable
blocked_structural_placement
unsupported
```

Score, HTTP 2xx и “best-looking result” не выбирают победителя. Конфликтующие revisions не подменяют друг друга. Все результаты имеют `authority_state=non_authoritative`, `production_ready=false` и сохраняются только как private shadow artifacts.

## Regression и safety proof

- focused Goal 2/3 + closed-world bundle: 36 passed;
- полный service suite: 311 passed, 5 внешних PyMuPDF SWIG deprecation warnings;
- Goal 1 compact: 14 decisions, 9 accepted, 5 blocked; production selection unchanged;
- exact candidate accounting: 1,351/1,351, без duplicates/unowned/omitted;
- provider counts: 19/19 внутри guard, calibration error 0.0%;
- Gate 2 source-fact bundle SHA-256 неизменён: `9E7E3FA0BE71C912FC4DE2B69D1B3447E90012B9FB89894E143C8A5EB8300F81`;
- Gate 2 domain bundle SHA-256 неизменён: `220BA58A59F33CA2F536D3A61B6959662A5F12E88640236438DEAC5A9523C454`;
- OCR, whole-PDF provider path, Knowledge/RAG/vector, OpenWebUI core patch и cleanup activation: не использовались;
- customer values, crops, raw responses и private paths в safe evidence/report: отсутствуют.

Controlled safe evidence:

- PDF SHA-256: `79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d`;
- safe evidence: `local/stage2/broker_reports_pdf_hybrid_reliability_2026-07-13-live3/evidence.safe.json`;
- safe evidence SHA-256: `C269AFB65AF764070831157C318D83D5CABA99C765B2B7E7040F09FF670C6F74`;
- private ArtifactStore SHA-256: `A4D6A15B69A59CCB8169754C6C114F3C147E52F9E8351BF37A646A4C9E596B85`;
- reference status: `agent_visual_reviewed_pending_human_signoff`.

Human signoff reference остаётся обязательным для будущих accuracy/production claims. Он не мешает этому engineering closure, потому что ни один provisional diagnostic не дал authority и каждый structural conflict завершился fail-closed.

## Gate 2 shadow E2E readiness

Все обязательные классы либо прошли (`5:3`), либо завершились обоснованным typed terminal (`1:3`, `3:2`, `4:1`, `4:2`). Контекст, provenance, placement, continuation, repeatability и arbitration contracts работоспособны и проверены. Поэтому вертикаль готова к отдельному Gate 2 shadow E2E integration slice.

Это не разрешает production Gate 2, не подключает текущие hybrid results к handoff и не делает blocked tables приемлемыми.

## Final statuses

```text
BROKER_REPORTS_PDF_HYBRID_CONTEXT_COMPACTION_READY
BROKER_REPORTS_PDF_HYBRID_ROW_WINDOWING_READY
BROKER_REPORTS_PDF_HYBRID_TOKEN_ESTIMATOR_CALIBRATED
BROKER_REPORTS_PDF_HYBRID_PLACEMENT_VALIDATION_READY
BROKER_REPORTS_PDF_CONTINUATION_CONTRACT_READY
BROKER_REPORTS_PDF_HYBRID_REPEATABILITY_GATE_READY
BROKER_REPORTS_PDF_HYBRID_SHADOW_ARBITRATION_READY
BROKER_REPORTS_PDF_HYBRID_RELIABILITY_PROOF_COMPLETED
BROKER_REPORTS_PDF_HYBRID_VERTICAL_READY_FOR_GATE2_SHADOW_E2E
```
