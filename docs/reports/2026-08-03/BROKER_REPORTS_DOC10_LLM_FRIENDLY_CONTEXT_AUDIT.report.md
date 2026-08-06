# Broker Reports DOC10 — LLM-friendly context audit and three-arm test

Дата: 2026-08-03  
Статус: research-only, completed; product pipeline и DOC6 не изменялись.

## Вывод простыми словами

DOC9-пакет был перегружен. Полный parser text полезен и уже доказан как лексически полный, но вторая ID-картинка визуально загрязнена длинными подписями, а длинные ID заметно раздувают JSON. Удаление ID map и сокращение ID действительно снижают tokens, цену и latency, но качество изменилось разнонаправленно между моделями. Ни один из 18 вариантов `model × arm` не прошёл исследовательский LLM-friendly порог.

Итог: `SECOND_ID_IMAGE_NEEDED=MODEL_DEPENDENT`, `SHORT_IDS_IMPROVE_RESULTS=MODEL_DEPENDENT`, `BEST_CONTEXT_PACKAGE=NO_CLEAR_WINNER`, `LLM_FRIENDLY_CONTEXT_PROJECTION=NOT_CONFIRMED`, `BEST_CHEAP_MODEL=NONE`.

## Границы и frozen protocol

- Таблицы: ровно 4 заданных, не менялись после outputs.
- Arms: 3; модели: 6; calls: 72/72; одна попытка; retry/fallback/best-of/repair/tools/web/retrieval: 0.
- Protocol SHA-256: `44589985ce979aae1cdacaad0b86c79364756274f55abb2a5d5653161bb54bb3`.
- Все 12 package hashes прошли повторную проверку.
- Parser lexical coverage не переоткрывался; `word_x_tolerance=0.5` сохранён как установленный факт.
- Parser source и DOC6 source не менялись.

## Визуальный аудит 12 original crops и ID maps

Все 24 изображения были открыты агентом до model calls. Геометрический итог: 360 пар label-label пересеклись; 349 labels пересекают source-text bbox; 362 labels пересекают длинные линии. Обрезанные края обнаружены в 5/12, заголовки — в 2/12.

| Таблица | Crop px | IDs | label-label pairs | labels↔text | labels↔lines | край обрезан | heading обрезан |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| unseen_pdf_03_t01 | 393×295 | 17 | 7 | 12 | 0 | нет | нет |
| unseen_pdf_02_t05 | 760×293 | 27 | 2 | 3 | 14 | нет | нет |
| unseen_pdf_01_t04 | 1523×254 | 34 | 9 | 25 | 6 | нет | нет |
| unseen_pdf_06_t25 | 1519×827 | 165 | 82 | 59 | 37 | да | нет |
| unseen_pdf_06_t03 | 1519×412 | 135 | 42 | 25 | 82 | да | нет |
| unseen_pdf_06_t35 | 1519×367 | 38 | 10 | 7 | 14 | нет | да |
| unseen_pdf_06_t27 | 1519×380 | 121 | 40 | 25 | 68 | да | нет |
| unseen_pdf_06_t09 | 1519×412 | 135 | 44 | 25 | 82 | да | нет |
| unseen_pdf_06_t05 | 1519×401 | 46 | 14 | 7 | 22 | нет | нет |
| unseen_pdf_01_t01 | 1523×1399 | 129 | 23 | 100 | 0 | нет | нет |
| unseen_pdf_06_t07 | 1519×861 | 176 | 80 | 61 | 37 | да | нет |
| unseen_pdf_01_t05 | 1523×174 | 16 | 7 | 0 | 0 | нет | да |

## Fragment-count и granularity

Всего 1039 fragments, 442 уникальных raw texts, 597 повторов сверх первого; numeric=319, currency-marker=7, single-character=35. Средняя длина fragment=6.120 символа. Inventory занимает 56319 UTF-8 bytes при 6359 символах полезного fragment text.

| Таблица | Fragments | Unique text | Duplicates | Numeric | Currency | 1-char | Avg chars | Inventory bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| unseen_pdf_03_t01 | 17 | 16 | 1 | 5 | 0 | 0 | 5.353 | 910 |
| unseen_pdf_02_t05 | 27 | 22 | 5 | 2 | 0 | 0 | 5.889 | 1458 |
| unseen_pdf_01_t04 | 34 | 26 | 8 | 9 | 2 | 2 | 5.088 | 1808 |
| unseen_pdf_06_t25 | 165 | 102 | 63 | 34 | 0 | 3 | 6.200 | 8952 |
| unseen_pdf_06_t03 | 135 | 91 | 44 | 61 | 0 | 8 | 6.089 | 7319 |
| unseen_pdf_06_t35 | 38 | 32 | 6 | 12 | 0 | 0 | 5.868 | 2050 |
| unseen_pdf_06_t27 | 121 | 82 | 39 | 54 | 0 | 7 | 5.967 | 6545 |
| unseen_pdf_06_t09 | 135 | 91 | 44 | 61 | 0 | 7 | 6.326 | 7351 |
| unseen_pdf_06_t05 | 46 | 39 | 7 | 12 | 0 | 0 | 6.174 | 2495 |
| unseen_pdf_01_t01 | 129 | 87 | 42 | 28 | 4 | 4 | 6.240 | 7000 |
| unseen_pdf_06_t07 | 176 | 109 | 67 | 37 | 0 | 3 | 6.386 | 9581 |
| unseen_pdf_01_t05 | 16 | 16 | 0 | 4 | 1 | 1 | 4.938 | 850 |

## Token overhead ID и общая нагрузка

Длинный ID всегда имеет 10 символов. Для всех 12 inventories только ID дают pre-call estimate 6769 OpenAI `o200k_base` tokens (в среднем 6.515 на ID). Google/Anthropic pre-call числа в audit — явно помеченные deterministic estimates; authoritative billing counts взяты из provider receipts.

На четырёх тестовых таблицах short IDs уменьшили inventory `o200k_base` estimate с 8839 до 6936 tokens. Реальный суммарный provider input для 24 B-calls против 24 C-calls: 92273 → 78961 tokens (-14.43%). Максимальный model-visible package: 531237 bytes.

## Модели и цены на дату freeze

| Key | Provider | Requested/resolved ID | Stability | Input / MTok | Output / MTok | Thinking policy |
| --- | --- | --- | --- | ---: | ---: | --- |
| openai_nano | openai | `gpt-5.4-nano-2026-03-17` | snapshot | $0.20 | $1.25 | reasoning.effort omitted; provider default none |
| openai_mini | openai | `gpt-5.4-mini-2026-03-17` | snapshot | $0.75 | $4.50 | reasoning.effort omitted; provider default none |
| google_31_flash_lite | google | `models/gemini-3.1-flash-lite` | stable selector; no dated immutable snapshot exposed | $0.25 | $1.50 | thinking configuration omitted; output price includes thinking tokens |
| google_35_flash_lite | google | `models/gemini-3.5-flash-lite` | stable selector; no dated immutable snapshot exposed | $0.30 | $2.50 | thinking configuration omitted; output price includes thinking tokens |
| anthropic_haiku_45 | anthropic | `claude-haiku-4-5-20251001` | dated snapshot | $1.00 | $5.00 | thinking omitted; no adaptive thinking |
| anthropic_sonnet_5 | anthropic | `claude-sonnet-5` | dateless pinned model ID | $2.00 | $10.00 | adaptive thinking provider default; output usage billed as output tokens |

Google `gemini-2.5-flash-lite` не повторялся: в DOC9 он дал 12×HTTP 404, поэтому до freeze заменён на доступный `gemini-3.1-flash-lite`. Sonnet 5 посчитан по вводной цене $2/$10, действующей до 2026-08-31.

## Arm A / B / C — общий результат

| Arm | Raw valid | Normalized valid | Fenced | Invented | Missing | Duplicated | Row recall | Cell recall | Token placement | Exact | Cost | Avg latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DOC9_BASELINE | 2/24 | 7/24 | 12 | 31 | 752 | 258 | 8.94% | 8.52% | 6.85% | 3/24 | $0.333689 | 18.818s |
| ONE_IMAGE_LONG_IDS | 2/24 | 5/24 | 11 | 36 | 1149 | 252 | 7.32% | 6.11% | 4.78% | 3/24 | $0.316114 | 16.601s |
| ONE_IMAGE_SHORT_IDS | 2/24 | 5/24 | 13 | 80 | 1129 | 412 | 8.54% | 6.11% | 5.73% | 3/24 | $0.273473 | 12.947s |

Normalizer удалял только внешние пробелы и ровно один внешний `json` fence. Он не исправлял JSON, IDs, rows или cell groups. Raw validity: 2/24 во всех трёх arms; normalized validity: A=7/24, B=5/24, C=5/24.

## Каждая дешёвая модель

Формат integrity: `invented/missing/duplicated`.

| Model | Arm | Norm valid | Integrity | Row recall | Cell recall | Token placement | Exact | Cost | Avg latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| openai_nano | DOC9_BASELINE | 0/4 | 15/24/163 | 0.00% | 0.00% | 0.00% | 0/4 | $0.010358 | 15.769s |
| openai_nano | ONE_IMAGE_LONG_IDS | 0/4 | 13/57/119 | 0.00% | 0.00% | 0.00% | 0/4 | $0.008644 | 11.754s |
| openai_nano | ONE_IMAGE_SHORT_IDS | 0/4 | 41/26/161 | 0.00% | 0.00% | 0.00% | 0/4 | $0.006353 | 9.112s |
| openai_mini | DOC9_BASELINE | 1/4 | 3/259/3 | 4.88% | 5.34% | 3.50% | 0/4 | $0.018077 | 9.136s |
| openai_mini | ONE_IMAGE_LONG_IDS | 0/4 | 4/287/6 | 0.00% | 0.00% | 0.00% | 0/4 | $0.015038 | 6.030s |
| openai_mini | ONE_IMAGE_SHORT_IDS | 1/4 | 3/305/4 | 7.32% | 4.58% | 3.82% | 0/4 | $0.013156 | 5.777s |
| google_31_flash_lite | DOC9_BASELINE | 1/4 | 3/36/12 | 12.20% | 6.87% | 5.41% | 1/4 | $0.013909 | 11.463s |
| google_31_flash_lite | ONE_IMAGE_LONG_IDS | 1/4 | 0/188/10 | 2.44% | 6.87% | 3.50% | 0/4 | $0.013148 | 7.620s |
| google_31_flash_lite | ONE_IMAGE_SHORT_IDS | 0/4 | 28/153/75 | 0.00% | 0.00% | 0.00% | 0/4 | $0.007759 | 5.331s |
| google_35_flash_lite | DOC9_BASELINE | 2/4 | 5/13/8 | 17.07% | 16.03% | 14.33% | 1/4 | $0.023536 | 9.554s |
| google_35_flash_lite | ONE_IMAGE_LONG_IDS | 1/4 | 3/183/34 | 2.44% | 6.87% | 3.50% | 0/4 | $0.021702 | 7.348s |
| google_35_flash_lite | ONE_IMAGE_SHORT_IDS | 2/4 | 7/197/51 | 17.07% | 16.03% | 14.33% | 1/4 | $0.013865 | 6.723s |
| anthropic_haiku_45 | DOC9_BASELINE | 1/4 | 5/109/72 | 2.44% | 6.87% | 3.50% | 0/4 | $0.039008 | 16.692s |
| anthropic_haiku_45 | ONE_IMAGE_LONG_IDS | 1/4 | 16/123/83 | 12.20% | 6.87% | 5.41% | 1/4 | $0.034191 | 15.377s |
| anthropic_haiku_45 | ONE_IMAGE_SHORT_IDS | 0/4 | 1/137/121 | 0.00% | 0.00% | 0.00% | 0/4 | $0.022771 | 8.356s |
| anthropic_sonnet_5 | DOC9_BASELINE | 2/4 | 0/311/0 | 17.07% | 16.03% | 14.33% | 1/4 | $0.228802 | 50.292s |
| anthropic_sonnet_5 | ONE_IMAGE_LONG_IDS | 2/4 | 0/311/0 | 26.83% | 16.03% | 16.24% | 2/4 | $0.223392 | 51.477s |
| anthropic_sonnet_5 | ONE_IMAGE_SHORT_IDS | 2/4 | 0/311/0 | 26.83% | 16.03% | 16.24% | 2/4 | $0.209570 | 42.385s |

Ни одна строка не имеет `llm_friendly_threshold_passed=true`; поэтому `BEST_CHEAP_MODEL=NONE`.

## Эффект второй ID-картинки (A против B)

Положительный delta означает преимущество A; cost/latency показаны отдельно и не входят в quality classification.

| Model | Effect | Δ norm validity | Δ row | Δ cell | Δ cost/table | Δ latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| openai_nano | NO_MEANINGFUL_EFFECT | -0.00 | -0.000 | -0.000 | +0.000429 | +4.015s |
| openai_mini | POSITIVE | +0.25 | +0.049 | +0.053 | +0.000760 | +3.106s |
| google_31_flash_lite | POSITIVE | -0.00 | +0.098 | -0.000 | +0.000190 | +3.843s |
| google_35_flash_lite | POSITIVE | +0.25 | +0.146 | +0.092 | +0.000458 | +2.206s |
| anthropic_haiku_45 | NEGATIVE | -0.00 | -0.098 | -0.000 | +0.001204 | +1.315s |
| anthropic_sonnet_5 | NEGATIVE | -0.00 | -0.098 | -0.000 | +0.001352 | -1.185s |

Итог: `MODEL_DEPENDENT`. A помог OpenAI mini и обеим Google, ухудшил row recall у обеих Anthropic, Nano не изменился. Следовательно универсально утверждать необходимость второй картинки нельзя.

## Эффект short IDs (B против C)

Положительный delta означает преимущество C.

| Model | Effect | Δ norm validity | Δ row | Δ cell | Δ cost/table | Δ latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| openai_nano | NO_MEANINGFUL_EFFECT | +0.00 | +0.000 | +0.000 | -0.000573 | -2.642s |
| openai_mini | POSITIVE | +0.25 | +0.073 | +0.046 | -0.000470 | -0.253s |
| google_31_flash_lite | NEGATIVE | -0.25 | -0.024 | -0.069 | -0.001347 | -2.289s |
| google_35_flash_lite | POSITIVE | +0.25 | +0.146 | +0.092 | -0.001959 | -0.625s |
| anthropic_haiku_45 | NEGATIVE | -0.25 | -0.122 | -0.069 | -0.002855 | -7.021s |
| anthropic_sonnet_5 | NO_MEANINGFUL_EFFECT | +0.00 | +0.000 | +0.000 | -0.003456 | -9.092s |

Итог: `MODEL_DEPENDENT`. C помог OpenAI mini и Google 3.5, ухудшил Google 3.1 и Haiku; Nano и Sonnet были нейтральны по четырём quality metrics. При этом C был самым дешёвым и быстрым arm в aggregate.

## Полностью восстановленные таблицы

| Table | Model | Arm |
| --- | --- | --- |
| unseen_pdf_01_t04 | anthropic_sonnet_5 | DOC9_BASELINE |
| unseen_pdf_01_t04 | google_35_flash_lite | DOC9_BASELINE |
| unseen_pdf_01_t04 | anthropic_sonnet_5 | ONE_IMAGE_LONG_IDS |
| unseen_pdf_01_t04 | anthropic_sonnet_5 | ONE_IMAGE_SHORT_IDS |
| unseen_pdf_01_t04 | google_35_flash_lite | ONE_IMAGE_SHORT_IDS |
| unseen_pdf_03_t01 | google_31_flash_lite | DOC9_BASELINE |
| unseen_pdf_03_t01 | anthropic_haiku_45 | ONE_IMAGE_LONG_IDS |
| unseen_pdf_03_t01 | anthropic_sonnet_5 | ONE_IMAGE_LONG_IDS |
| unseen_pdf_03_t01 | anthropic_sonnet_5 | ONE_IMAGE_SHORT_IDS |

Всего 9/72 exact outputs: только `unseen_pdf_03_t01` и `unseen_pdf_01_t04`. `unseen_pdf_06_t03` и `unseen_pdf_06_t07` не были восстановлены полностью ни одной моделью ни в одном arm.

## Оставшиеся ошибки

`ID_CONSERVATION_INVALID`=44, `STRUCTURE_NOT_EXACT`=8, `JSON_PARSE_ERROR`=6, `EMPTY_OR_INVALID_CELL`=2, `ROWS_OR_UNRESOLVED_INVALID`=3. Основной класс — нарушение ID conservation; затем structural miss при валидном JSON, parse/shape errors. Все 4 таблицы остались в каждом знаменателе.

## Цена, latency и лучший package

Общая стоимость 72 calls: $0.923276. Aggregate cost: A=$0.333689, B=$0.316114, C=$0.273473. Средняя latency: A=18.818s, B=16.601s, C=12.947s.

`BEST_CONTEXT_PACKAGE=NO_CLEAR_WINNER`: C дешевле и быстрее, но не доминирует A/B по validity, row/cell recall и conservation; A имеет лучшие aggregate quality metrics, но его эффект модель-зависим и пакет дороже. Weighted score не использовался.

## Acceptance

```text
CONTEXT_PACKAGE_AUDIT_COMPLETED = TRUE
ALL_12_DOC9_PACKAGES_AUDITED = TRUE
TABLES_TOTAL = 4
CONTEXT_ARMS_TOTAL = 3
MODELS_TOTAL = 6
EXPECTED_CALLS_TOTAL = 72
ALL_CALLS_ACCOUNTED = TRUE
PACKAGE_HASH_PARITY = PASSED
PROMPT_CHANGED_DURING_RUN = FALSE
PARSER_CHANGED = FALSE
DOC6_CHANGED = FALSE
FAILED_TABLES_EXCLUDED_TOTAL = 0
RAW_AND_NORMALIZED_RESULTS_REPORTED = TRUE
SECOND_IMAGE_EFFECT_REPORTED = TRUE
SHORT_ID_EFFECT_REPORTED = TRUE
QUALITY_AND_COST_REPORTED = TRUE
```

## Финальный статус

```text
DOC10_EXPERIMENT = COMPLETED
SECOND_ID_IMAGE_NEEDED = MODEL_DEPENDENT
SHORT_IDS_IMPROVE_RESULTS = MODEL_DEPENDENT
BEST_CONTEXT_PACKAGE = NO_CLEAR_WINNER
LLM_FRIENDLY_CONTEXT_PROJECTION = NOT_CONFIRMED
BEST_CHEAP_MODEL = NONE
```

После этого эксперимента product pipeline не реализован и модель не активирована.
