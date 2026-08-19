# G5.72 — Visual Markdown → Semantic Classifier Microstand

Дата: 2026-08-16

Статус: `CLOSED_INTERMEDIATE_PROVEN_CLASSIFICATION_NOT_RELIABLE`

## Terminal

```text
VISUAL_MARKDOWN_INTERMEDIATE_PROVEN
IMAGE_TO_MARKDOWN_SEMANTIC_NEUTRALITY_PROVEN
MARKDOWN_PRESERVES_METADATA_LAYOUT
SAME_MARKDOWN_CROSS_MODEL_CLASSIFICATION_MEASURED
GEMINI_IMPROVES_ON_MARKDOWN
MARKDOWN_CLASSIFICATION_NOT_RELIABLE
NO_EXTRA_SEMANTIC_LAYER_ADDED
FINANCIAL_GENERALIZATION_PRESERVED
```

## Короткий вывод

Нейтральный промежуточный Markdown доказан на B/F/C: Gemini перенесла исходные visual regions без потери текста, переименования labels, разрыва label/value связей или изменения value boundaries. В Case F label остался буквально `Код клиента`; account-смысл на transcription stage не появился.

Разделение vision и semantics действительно помогло Gemini на главной боли: Case F, который image→semantic путь ошибочно превращал в account, на frozen Markdown прошёл exact. Более сильная модель также правильно abstain на этом case.

Но общий двухступенчатый путь пока ненадёжен. Gemini добавила один unsupported fact на C, а strong model потеряла broker fact и границу agreement value на B. Ни один classifier не прошёл B/F/C целиком, поэтому repeatability и untouched holdout не запускались.

## Reuse и доменные границы

Stage 1 использовал существующий `PdfGridExperimentProviderFactory.create_for_openwebui()`:

```text
PNG region → Gemini → { markdown }
```

Model-visible transcription view не содержал слова `metadata` и ни одной из 11 contract roles. JSON wrapper был только transport contract вокруг одного Markdown string.

Stage 2 использовал существующие provider owners:

- Gemini text arm: `Gate2StructuredModelClientFactory.create()`;
- strong text arm: `PdfDualVlmFactProviderFactory.create_for_openwebui()` и новый text-only entrypoint существующего OpenAI Responses owner.

Strong model был заморожен до результатов как `gpt-5.6-sol`. Первоначальный Gate2/OpenWebUI chat route сделал три provider submissions, но не дал model output: frozen model отсутствовал в live `/api/models`. Вместо смены модели или prompt был добавлен минимальный text-only entrypoint в уже существующий native Responses owner. Отдельный strong-only technical replay использовал тот же Markdown, instruction и schema; Gemini повторно не запускалась.

Product metadata path, ontology и publication owner не менялись. Product activation: `0`.

## Stage 1 — human visual audit

| Case | Lost text | Invented text | Semantic rewrite | Broken pairs | Broken structure | Changed boundaries | Итог |
|---|---:|---:|---:|---:|---:|---:|---|
| B | 0 | 0 | 0 | 0 | 0 | 0 | qualified |
| F | 0 | 0 | 0 | 0 | 0 | 0 | qualified |
| C | 0 | 0 | 0 | 0 | 0 | 0 | qualified с known oracle-scope gap |

Case C содержит частично видимую паспортную строку. Markdown честно перенёс её, но старый frozen truth её не включает. Truth после output не менялся; расхождение явно сохранено как pre-existing oracle-scope gap.

Stage 1: `3` single-shot submissions, transport/schema failures `0`, usage `3 832` tokens, wall duration `5 563 ms`. Markdown после human qualification не редактировался и не регенерировался.

## Stage 2 — одинаковый Markdown, разные модели

| Case | Visual/Markdown truth | Gemini | Strong model |
|---|---|---|---|
| B | 5 facts, layout pairs preserved | 5/5 exact | 3 correct; broker missed; agreement boundary changed |
| F | person name; client code вне contract | exact; account fact absent | exact; account fact absent |
| C | 3 frozen facts; partial passport line retained separately | 3 correct + extra `PERSON_CITIZENSHIP` | 3/3 exact |

Gemini semantic arm: `3` valid submissions, usage `6 806` tokens, duration `20 485 ms`.

Strong semantic arm: первые `3` attempts были pre-output technical failures; после owner correction — `3` valid submissions, usage `3 474` tokens, duration `22 083 ms`.

Для обеих моделей совпадали:

- immutable Markdown hashes;
- metadata contract `1.0.0`, 11 fact types;
- semantic instruction hash;
- canonical output schema hash;
- model-specific prompt: `0`.

## Что доказано и что не доказано

Доказано:

1. Visual region можно превратить в прозрачный, human-auditable Markdown без semantic rewrite на трёх representative layouts.
2. Markdown сохраняет B layout и F label буквально.
3. Gemini на Markdown перестала делать известную ошибку `client code → account`.
4. Ошибки после хорошего Markdown зависят от classifier: Gemini ошиблась на C, strong model — на B.

Не доказано:

1. Ни один classifier не прошёл все B/F/C одним clean run.
2. KISS two-stage path не квалифицирован для repeatability или holdout.
3. Product integration не разрешена.

Третий verifier, semantic repair, voting, blacklist и broker rules не добавлялись.

## Repeatability и holdout

Repeatability: `NOT_EXECUTED`. Условие — хотя бы один classifier проходит B/F/C одним clean run — не выполнено.

Untouched holdout: `NOT_EXECUTED`. Стабильного development candidate нет; holdout не использовался как дополнительный tuning corpus.

## Guardrails и regression

- broker hints, metadata hints на Stage 1, regex и synonym dictionaries: `0`;
- manual Markdown repair, retries, best-of-N, voting, judge и result selection: `0`;
- focused regression после bundle rebuild: `178 passed`;
- финальные owner/harness tests: `20 passed`;
- Ruff и compileall: passed;
- generated bundle matches maintained source;
- financial Holdout A: `39`, Holdout B: `129`, exact frozen equality `true`, source stores unchanged `true`.

Private crops, source PDFs, raw Markdown, human audit, immutable freezes, exact model-visible requests, raw outputs и technical failures сохранены во внешнем private evidence bundle. В Git находятся только proof harness, owner tests и safe closeout. Commit, push и PR не выполнялись.
