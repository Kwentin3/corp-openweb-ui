# Broker Reports PDF: VLM-guided intake refactor

Дата проверки: 2026-07-15
Режим: default-disabled research/shadow
Production Gate 2 authority: без изменений

## Короткий вывод

Идея подтверждена и проведена через основной локальный контракт: parser больше
не обязан заранее узнавать привычный тип таблицы. Он сохраняет точные слова,
координаты, crop identity и source refs. В candidate-crop запросе VLM получает
ограниченное изображение и точный текст слов с анонимными id и bbox; в
page-level запросе — только строго идентифицированное изображение страницы.
VLM предлагает физическую структуру, а deterministic
assembly/materialization либо доказывает её на исходных атомах, либо блокирует,
либо сохраняет неоднозначность.

При этом slice пока нельзя объявить готовым для внешнего shadow E2E. Локальный
candidate/page synthetic E2E и regressions существуют, но нет законченного one-call
development matrix runner, нового source-frozen unseen holdout и прошедшего
live canary с repo/live bundle parity. Эти доказательства нельзя заменить
старыми two-attempt артефактами.

## До и после

| Область | До | После этого slice |
|---|---|---|
| Intake | Один смешанный `eligible=false`: plausibility, техническая возможность и holdout usefulness слиты | Три независимых checksummed решения: detection, processability, holdout |
| Необычная форма | Rows, coverage, sparse/empty bands и другие признаки могли выглядеть как hard rejection | Эти признаки остаются metadata; hard block создают только доказанные identity, geometry, ownership, crop, schema или budget failures |
| Inventory overflow | Общий cap мог стереть уже завершённые страницы через `pages=[]` | Сохраняется полностью завершённый prefix, crossing page и весь tail явно помечаются missing/partial |
| Candidate VLM | Legacy structural-repair использовал два независимых вызова и consensus | Отдельный default-disabled guided route допускает один `countTokens`, максимум один generate, без retry/failover |
| Page proposal | Отсутствовал bounded closed contract | Есть page-level proposal: одна страница, ноль atoms до ответа, максимум два непересекающихся bbox |
| Строгость | Сильная строгость могла стоять до интерпретации | Hard technical gate остаётся до VLM; основная структурная строгость стоит после proposal и проверяет точные source atoms |
| Семантика | Риск смешать header meaning с физической сеткой | Semantic-header projection остаётся отдельным downstream shadow, не выбирает и не чинит topology |

## Независимые intake-решения

Новый factory-owned internal contract возвращает:

- detection: `plausible | implausible | uncertain | absent_due_to_upstream_failure`;
- processability: `processable | unsupported` с закрытым точным reason code;
- holdout: `selected | not_selected | not_evaluated`.

Rows, columns, density, page coverage, empty bands, parser strategy и необычная
глубина заголовка допускаются только в `metadata`. Validator пересчитывает
processability из технических фактов и checksum, поэтому morphology не может
незаметно превратиться в hard block. Каждое решение закрыто привязано к
document/PDF SHA/page/scope/evidence identity. После provider `countTokens`
candidate state и page composite получают финальное решение с фактическим
числом токенов; over-budget или upstream failure переводят его в точный
unsupported terminal. Технически неподдерживаемый вход завершается до provider:
`0 countTokens / 0 generate`. Legacy route этого поля не получает.

Успешный VLM-ответ `absent` теперь финализирует только detection как
`implausible` и считается нормальным отрицательным результатом, а не internal
processing failure. `uncertain` финализирует detection как `uncertain` и
остаётся явным `consensus_not_reached`; processability в обоих случаях не
подменяется.

Этот контракт пока не является доказательством качества detection classifier:
development runner, который отдельно классифицирует все 27 audited scopes и
обычные negative pages, ещё не реализован.

## Partial-prefix recovery

Существующий limit `75 000` inventory objects не повышался. При crossing:

- все полностью завершённые страницы до crossing остаются на месте;
- crossing page не выдаётся за complete;
- для всего tail создаются явные partial placeholders;
- документ получает `pdf_layout_document_inventory_budget_exceeded`;
- tail получает `pdf_layout_page_not_processed_document_inventory_budget`;
- diagnostics содержат source/completed/missing page counts, первый missing
  page, retained/would-be object counts и прежний limit.

Реальная read-only проверка двух development-only IBKR PDF после изменения:

| PDF | Статус | Всего страниц | Завершено | Первый missing | Missing tail | Retained objects | Would-be at crossing | Сохранённые candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| IBKR audited 2025 | partial | 29 | 21 | 22 | 8 | 72 657 | 78 687 | 21 |
| IBKR midyear 2025 | partial | 21 | 19 | 20 | 2 | 72 080 | 77 639 | 20 |

Это recovery bounded prefix, а не full-document detection: поздние таблицы в
missing tail всё ещё недоступны. Такой предел зафиксирован явно, а не спрятан
под «таблиц нет».

## VLM proposal contract

Factory-owned proposal использует существующие canonical JSON и
request/response/package schemas с отдельной closed revision. Новый parser,
OCR, solver framework или wire format не добавлялись.

Candidate-crop package:

- одна bounded crop;
- максимум один proposed region внутри normalized scope;
- от 1 до 1 000 atoms: анонимный id, bbox, source order и точный parser text;
- document/page/table refs, checksums, private candidate ids и business
  authority не входят в model JSON;
- максимум 48 KiB model JSON и 20 000 counted input tokens.

Page-level package:

- одна rendered page;
- `atoms=[]` до region proposal;
- максимум два positive-area, finite, non-overlapping regions;
- те же JSON, token, output и image bounds.

Response закрыто описывает `present | absent | uncertain`, bbox, border
evidence, density, continuation likelihood, row/column boundaries, header-row
count, spans, hierarchy, alternatives и uncertainty codes. Parser thresholds,
validator bypass, corrected financial values, confidence winner и unrestricted
configuration запрещены схемой.

## Candidate-crop execution

Отдельный guided runtime не переиспользует legacy two-attempt consensus loop.
На один target допустимы:

- ровно один `countTokens`;
- generate только если counted input прошёл hard limit;
- максимум один generate;
- attempt number всегда `1`, lineage пуст;
- zero retry и zero provider failover.

Acceptance возможен только при одном полном bound hypothesis. Multiple
alternatives, uncertainty и unsupported не ранжируются и не «чинятся» —
материализация не создаётся. Accepted physical structure доказывает exact
ownership, bbox-to-cell compatibility, certified separator preservation,
валидные spans/headers, crop/parser identity и source-only materialization с
нулём invented, omitted, duplicated и mutated values.

Legacy `run_target` и его two-attempt research semantics оставлены отдельно;
production Gate 2 selection не менялась.

Guided shadow теперь отправляет именно candidate-region proposal, а не старый
topology-only request. Полный bbox `[0,0,1,1]` детерминированно переводится в
существующий exact assembly/materialization contract. Изменённый bbox не
принимается старым путём: он fail-closed требует exact reselection. Отдельный
provider-free binder уже доказывает included/excluded/crossing accounting и
может материализовать такой bbox в unit proof, но candidate-adjustment ветка
ещё не подключена к shadow orchestration и не сертифицирована на audited
matrix. Это оставшийся функциональный дефект, а не скрытый успешный результат.

## Page-level execution

Локально реализован и подключён к default-disabled shadow closed page proposal
surface: ноль atoms, одна image, максимум два непересекающихся regions, строгие
presence, alternatives и uncertainty contracts. Маршрут выбирается только
явным allowlist, который по умолчанию пуст. Канонический ключ —
`document_ref::page_ref`; короткий `page_ref` принимается только если он
глобально уникален внутри package. Неоднозначный короткий ref не выбирает ни
одну страницу. Allowlisted page заменяет candidate targets этой страницы и
может быть создана даже при нуле parser candidates. Перед provider реальный PDF
`page.rect` строго сверяется с parser page identity, а полная same-page word
projection проверяется на уникальность и нахождение внутри страницы. Страница
без точной непустой word projection получает `unsupported` до model call.
`run_page_proposal_once` доказывает `1 countTokens / 0..1
generate`, zero retry/failover, checksummed result и non-authoritative state.

Provider-free `PdfVlmRegionBindingFactory` выполняет следующий deterministic
шаг: normalized bbox переводится обратно в исходные PDF coordinates, exact word
atoms перевыбираются, boundary-crossing blocks, parser geometry строится
существующей фабрикой, одна unambiguous topology связывается и materialization
использует только source values. Multiple hypotheses сохраняются как ambiguity.
До двух region crops рендерятся с нулевым padding. Proposal, binder result и
финализированные intake-решения сохраняются одним private non-authoritative
`broker_reports_pdf_vlm_guided_page_intake_result_v1`. `absent` и `uncertain`
не создают принятую структуру. Composite validator повторно проверяет binder
против исходной caller-owned text-layer projection, proposal package, parent
bbox и точных crop manifests; согласованной подмены вложенных checksum
недостаточно. Это локальный synthetic shadow E2E, но не
development-corpus, unseen-holdout или live proof.

## Development evidence

Audited v5 corpus окончательно считается development-only: 7 PDF и 27 parser
candidates. Предыдущий forensic audit показал:

- 4 настоящих bounded regions/fragments: Betterment p4, DriveWealth p7, p9,
  p11;
- 23 исходных bbox, которые нельзя принимать целиком: 22 broad prose/layout
  regions и один TOC;
- все 27 укладываются в downstream hard bounds: максимум 615 atoms при limit
  1 000, 55 rows при limit 64 и 10 columns при limit 24;
- не менее 10 настоящих Moomoo tables лежат внутри compound regions или вне
  parser candidate bbox;
- оба IBKR теперь сохраняют ранний bounded prefix вместо нулевого результата.

Это доказывает root cause и техническую processability, но не доказывает новую
VLM reconstruction accuracy. В этом запуске реальный provider по v5 matrix не
вызывался. Поэтому нельзя честно указать recovered real tables или measured
false-candidate suppression для нового hybrid route. Unit tests с controlled
provider boundary доказывают протокол вызовов и fail-closed behavior, а не
качество модели.

## Provider и context accounting

Доказанные contract limits:

| Route | Images | Atoms до proposal | Regions | Model JSON | Counted input | Count calls | Generate calls | Retry/failover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Candidate | 1 crop | 1..1 000 text+bbox atoms | <=1 | <=48 KiB | <=20 000 | 1 | 0 или 1 | 0 / 0 |
| Page | 1 page | 0 | <=2 | <=48 KiB | <=20 000 | 1 | 0 или 1 | 0 / 0 |

Full PDF, source ledger, parser grid, source refs, business prompt, human
reference и duplicated metadata в model JSON не входят. Точный текст слов в
candidate-crop входит намеренно; page-level до proposal сохраняет `atoms=[]`.
Private artifact сохраняет source authority отдельно. Реальная стоимость и
actual tokens пока не измерены на fresh holdout; любые цифры вместо этого были
бы выдумкой.

## Fresh unseen holdout

Не выполнен. В repository нет законченного one-call holdout runner + отдельного
post-seal scorer, который обеспечивал бы:

- новые, не встречавшиеся ранее PDF hashes;
- preregistered source/target selection без substitution;
- provider terminal seal до reference access;
- независимые detection, processability, reconstruction и holdout metrics;
- exact token/image/JSON/response accounting;
- checksum до и после scoring.

Старый v5/two-attempt holdout не использовался как подмена.

## Live shadow и parity

Live canary не запускался, потому что fresh-holdout prerequisite не выполнен.
Это преднамеренный stop, а не runtime success. Следовательно, этот отчёт не
заявляет live provider routing, cleanup/rollback или repo/live bundle parity.
Production flags и Gate 2 authority не повышались.

## Проверки repository

Локально выполнены focused contract tests для:

- independent intake decisions и morphology isolation;
- inventory overflow prefix/tail accounting;
- candidate/page proposal schemas и budgets;
- guided candidate one-call accounting;
- legacy/value-free candidate packages и page packages блокируются до provider;
- `1 001` candidate atoms блокируются при `0/0` provider calls, а hard maximum
  остаётся `1 000` вместе с отдельным лимитом `48 KiB`;
- ambiguous/unsupported/budget/provider terminals;
- `absent` как clean detection outcome и `uncertain` как отдельная ambiguity;
- page allowlist без fan-out при одинаковом `page_ref` в двух документах;
- anchored page composite против source projection, proposal и crop manifests;
- exact source-only assembly/materialization validation;
- shadow default-off и technical preflight `0/0`;
- legacy-route separation;
- неизменный default cap `75 000` и partial-prefix accounting;
- Gate 1 bundle closed-world order и default-false guided valves.

После финальной локальной сборки:

- service suite: `661 passed`, 5 прежних PyMuPDF/SWIG warnings;
- focused guided/bundle/canary suite: `144 passed`, те же 5 warnings;
- Ruff по изменённому runtime/contract/script/test контуру с исключением
  ожидаемого `E402` в generated bundle: `All checks passed`;
- `git diff --check`: ошибок whitespace нет (только предупреждения Git о
  будущей нормализации LF/CRLF в уже грязном Windows worktree);
- Gate 1 bundle SHA-256:
  `BB4A8E75092A8BB0E5C94B202DDE2452D9FA0D7A7E6BFC4DF9C30FD2A93816DE`.

Эти проверки не заменяют отсутствующие corpus/holdout/live доказательства.

## Оставшиеся unsupported / незакрытые случаи

1. Нет audited one-call development runner для Betterment, DriveWealth,
   compound/outside-bbox Moomoo и zero-call negatives.
2. Candidate bbox adjustment должен подключить существующий binder и получить
   persisted included/excluded/crossing accounting на реальных development
   cases.
3. Ранние qualification/parser/raster/package/full-page-identity failures всё
   ещё могут завершиться до создания трёх intake-решений; это нужно закрыть
   отдельным upstream terminal state, не выдавая такой случай за `absent`.
4. Нет genuinely unseen source-frozen holdout и независимого scorer.
5. Нет прошедшего default-disabled live canary и repo/live parity proof.
6. IBKR missing tail остаётся честно неподдержанным этим bounded prefix slice.

## Рекомендация для Gate 2

Оставить hybrid intake строго default-disabled и non-authoritative. Не менять
production Gate 2 selection. Следующий узкий шаг — завершить exact region
binding для adjusted candidate bbox и запись ранних upstream terminals, сделать
воспроизводимый development runner, затем отдельный frozen holdout. Live canary
разрешён только после прохождения этих стадий.

BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_PARTIAL
Candidate bbox adjustment и ранние preflight upstream intake states не закрыты; также нет one-call development matrix, нового unseen holdout и прошедшего live canary/parity.
