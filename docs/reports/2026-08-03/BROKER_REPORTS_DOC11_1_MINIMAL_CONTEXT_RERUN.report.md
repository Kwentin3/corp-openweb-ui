# Broker Reports DOC11.1 — clean rerun of minimal table context test

Дата: 2026-08-03  
Статус: **DOC11_1_EXPERIMENT = COMPLETED**

## Итог

Чистый rerun выполнен полностью: 16/16 новых слотов получили HTTP 200, retry/fallback отсутствуют, старые два DOC11 ответа не использованы в новой статистике.

Plain-text context улучшил структурные метрики относительно исторического DOC10 для двух дешёвых моделей и не изменил результат Haiku, поэтому `PLAIN_TEXT_CONTEXT_IMPROVES_STRUCTURE = CONFIRMED`. Но ни одна дешёвая модель не прошла обязательный порог валидности и text conservation, поэтому `MINIMAL_CONTEXT_PROJECTION = NOT_CONFIRMED` и `BEST_CHEAP_MODEL = NONE`.

Opus является только reference ceiling: 100% normalized validity и text conservation, 85.366% row recall, 95.420% cell-group recall, 98.408% placement и 2/4 exact tables. Это не подтверждает пригодность дешёвых моделей.

## Frozen inputs и accounting

- Использованы исходные четыре DOC11 packages без изменений; package hash verification — `PASSED`.
- Каждый model-visible package по-прежнему содержит только `table.png`, `parser_text.txt`, `prompt.txt`.
- Одно изображение на вызов; model-visible IDs, parser rows/columns/order/coordinates/DOC6/gold — 0.
- Exact models: `gpt-5.4-mini-2026-03-17`, `models/gemini-3.5-flash-lite`, `claude-haiku-4-5-20251001`, `claude-opus-5`.
- Новый protocol: `21cb52be6e88ae87f7d8bdd9fa62d7c3ff85219707e665a1987f6abfff8a0a03`.
- Fresh calls: 16; HTTP 200: 16; interrupted: 0; retry: 0; fallback: 0; excluded tables: 0.

## Результаты по моделям

| Модель | Calls | Raw valid | Normalized valid | Text conservation | Row recall | Cell recall | Placement | Exact tables | Cost/table | Avg latency |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| `openai_mini` | 4/4 | 25.000% | 25.000% | FAILED | 14.634% | 9.160% | 10.828% | 1/4 | $0.003485 | 6.343s |
| `google_flash_lite` | 4/4 | 50.000% | 50.000% | FAILED | 31.707% | 61.069% | 51.274% | 1/4 | $0.001518 | 4.037s |
| `anthropic_haiku` | 4/4 | 0.000% | 0.000% | FAILED | 0.000% | 0.000% | 0.000% | 0/4 | $0.003358 | 5.641s |
| `anthropic_opus` | 4/4 | 100.000% | 100.000% | PASSED | 85.366% | 95.420% | 98.408% | 2/4 | $0.049681 | 20.438s |

Ошибки:

- OpenAI Mini: 1 exact; по одному `ROWS_OR_UNRESOLVED_INVALID`, `TEXT_MULTISET_INVALID`, `JSON_PARSE_ERROR`.
- Gemini Flash-Lite: 1 exact; 1 structurally non-exact conserved table; 2 `TEXT_MULTISET_INVALID`.
- Claude Haiku: 3 `TEXT_MULTISET_INVALID`, 1 `CELL_INVALID`; exact tables отсутствуют.
- Claude Opus: 2 exact; ещё 2 valid+conserved, но structurally non-exact.

Полностью точные таблицы: `doc11_table_02` у OpenAI Mini, Gemini Flash-Lite и Opus; `doc11_table_01` у Opus.

## Контекст и экономика

| Модель | Input tokens | Output tokens | Thinking tokens | Total cost | Cost/table | Avg latency |
|---|---:|---:|---:|---:|---:|---:|
| OpenAI Mini | 5,014 | 2,262 | 0 | $0.013940 | $0.003485 | 6.343s |
| Gemini Flash-Lite | 6,729 | 1,621 | 0 | $0.006071 | $0.001518 | 4.037s |
| Claude Haiku | 5,806 | 1,525 | 0 | $0.013431 | $0.003358 | 5.641s |
| Claude Opus | 6,295 | 6,690 | 0 | $0.198725 | $0.049681 | 20.438s |

Общий расход: 23,844 input tokens, 12,098 output tokens, $0.2321667.

## Сравнение с DOC10

DOC10 не перезапускался. Для трёх дешёвых моделей совпадают exact model IDs и четыре таблицы; ближайший historical arm — `ONE_IMAGE_SHORT_IDS`.

- OpenAI Mini: structure `POSITIVE`, overload reduction `false`.
- Gemini Flash-Lite: structure `POSITIVE`, overload reduction `true`.
- Claude Haiku: `NO_MEANINGFUL_EFFECT`, overload reduction `true`.
- Opus: в DOC10 отсутствовал.

Итог: `PLAIN_TEXT_CONTEXT_REDUCES_OVERLOAD = INCONCLUSIVE`, потому что сокращение не воспроизвелось у всех трёх дешёвых моделей. Структурное улучшение подтверждено, но недостаточно для пригодности дешёвой модели.

## Финальные решения

| Решение | Статус |
|---|---|
| `DOC11_1_EXPERIMENT` | `COMPLETED` |
| `PLAIN_TEXT_CONTEXT_REDUCES_OVERLOAD` | `INCONCLUSIVE` |
| `PLAIN_TEXT_CONTEXT_IMPROVES_STRUCTURE` | `CONFIRMED` |
| `BEST_CHEAP_MODEL` | `NONE` |
| `BEST_REFERENCE_MODEL` | `anthropic_opus` |
| `MINIMAL_CONTEXT_PROJECTION` | `NOT_CONFIRMED` |

## Граница остановки

Parser, DOC6, product pipeline и model activation не менялись. Результат закрывает только DOC11.1 hypothesis test и не разрешает новую pipeline-итерацию.
