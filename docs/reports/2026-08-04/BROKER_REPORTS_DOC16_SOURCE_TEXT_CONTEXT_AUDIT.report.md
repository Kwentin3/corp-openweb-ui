# Broker Reports DOC16 — source-text context forensic audit

## Итог

- `DOC16_AUDIT = COMPLETED`
- `SOURCE_TEXT_CONTEXT_QUALITY = INSUFFICIENT`
- `SOURCE_TEXT_HYPOTHESIS_FAIRLY_TESTED = NO`
- `SOURCE_TEXT_DEFAULT_POLICY = OPTIONAL_OR_INCONCLUSIVE`
- fair packages: `5/24` при пороге `20/24`
- новых provider calls: `0`; parser/DOC6/product pipeline/Gate 2 не менялись.

## Что фактически получила модель

Для 94 завершённых Arm B вызовов независимо пересобран один provider-specific request: один PNG и один user-role text block, состоящий из базовой инструкции, SOURCE TEXT START/END и frozen fragment list. Все 94 request hashes совпали. Ещё 2 Anthropic Opus слота завершились transport failure до доказанного model-visible payload; intended request детерминированно пересобран, а отсутствие model-visible payload учтено отдельно. Всего accounted: `96/96`.

Содержимое изображения, инструкции, source text и канонической schema совпадало между четырьмя моделями для всех 24 таблиц. Различались только provider envelope, model id и provider-native schema wrapper. Source text находился в правильной роли, присутствовал ровно один раз, не имел текста после закрывающего delimiter и прошёл UTF-8 roundtrip.

| Model | Provider | Requested model | Arm B slots | Terminal | Finish |
|---|---|---|---:|---|---|
| `anthropic_haiku` | `anthropic` | `claude-haiku-4-5-20251001` | 24 | `{"COMPLETED": 24}` | `{"end_turn": 24}` |
| `anthropic_opus` | `anthropic` | `claude-opus-5` | 24 | `{"COMPLETED": 22, "FAILED": 2}` | `{"NO_PROVIDER_FINISH": 2, "end_turn": 22}` |
| `google_flash_lite` | `google` | `models/gemini-3.5-flash-lite` | 24 | `{"COMPLETED": 24}` | `{"STOP": 24}` |
| `openai_mini` | `openai` | `gpt-5.4-mini-2026-03-17` | 24 | `{"COMPLETED": 24}` | `{"completed": 24}` |

## Crop audit

Статусы: `{"CROP_CLEAN": 12, "CROP_CLIPPED": 7, "CROP_CONTAMINATED": 5}`. Все 24 PNG открыты в исходном разрешении; видимый текст читаем. Нечистые crops содержат обрезанные шапки/крайние колонки/примечания либо footer, соседнюю таблицу или иной page text. Изображения не исправлялись.

## Source-text quality

Critical-value coverage по таблицам: минимум `80.00%`, медиана `97.34%`, максимум `100.00%`. Пакетов ниже 99%: `12`. Все exact foreign/duplicate fragment entries сохранены только в private diff; safe surface публикует counts и classes.
Order: `{"ORDER_GOOD": 18, "ORDER_MISLEADING": 1, "ORDER_PARTIAL": 5}`. Это измерение существующей parser sequence относительно sealed visual-gold order, а не новый reading-order algorithm.

| Table | Crop | Critical coverage | Foreign fragments | Foreign critical | Duplicate critical | Split values | Order | Context class |
|---|---|---:|---:|---:|---:|---:|---|---|
| `ACORNS_T01` | `CROP_CLEAN` | 100.00% | 0 | 1 | 1 | 0 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |
| `ACORNS_T02` | `CROP_CLEAN` | 100.00% | 0 | 0 | 0 | 0 | `ORDER_GOOD` | `CONTEXT_CLEAN_BUT_UNHELPFUL` |
| `ACORNS_T03` | `CROP_CLEAN` | 100.00% | 0 | 0 | 0 | 0 | `ORDER_GOOD` | `CONTEXT_CLEAN_BUT_UNHELPFUL` |
| `JEFFERIES_T01` | `CROP_CONTAMINATED` | 99.22% | 5 | 1 | 0 | 1 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |
| `JEFFERIES_T02` | `CROP_CONTAMINATED` | 90.36% | 5 | 1 | 0 | 1 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |
| `JEFFERIES_T03` | `CROP_CLIPPED` | 100.00% | 5 | 3 | 0 | 0 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |
| `JEFFERIES_T04` | `CROP_CLIPPED` | 100.00% | 0 | 0 | 0 | 0 | `ORDER_GOOD` | `CONTEXT_INCOMPLETE` |
| `JEFFERIES_T05` | `CROP_CONTAMINATED` | 95.45% | 13 | 8 | 6 | 0 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |
| `JEFFERIES_T06` | `CROP_CONTAMINATED` | 100.00% | 5 | 3 | 1 | 0 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |
| `LPL_T01` | `CROP_CLEAN` | 90.00% | 6 | 5 | 0 | 0 | `ORDER_MISLEADING` | `CONTEXT_CONTRADICTORY` |
| `LPL_T02` | `CROP_CONTAMINATED` | 80.00% | 1 | 3 | 0 | 0 | `ORDER_PARTIAL` | `CONTEXT_CONTRADICTORY` |
| `LPL_T03` | `CROP_CLEAN` | 87.10% | 0 | 3 | 0 | 0 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |
| `LPL_T04` | `CROP_CLEAN` | 80.00% | 2 | 2 | 0 | 0 | `ORDER_PARTIAL` | `CONTEXT_CONTRADICTORY` |
| `OPPENHEIMER_T01` | `CROP_CLEAN` | 100.00% | 0 | 0 | 0 | 0 | `ORDER_GOOD` | `CONTEXT_CLEAN_BUT_UNHELPFUL` |
| `STONEX_T01` | `CROP_CLEAN` | 90.00% | 7 | 1 | 0 | 0 | `ORDER_PARTIAL` | `CONTEXT_CONTRADICTORY` |
| `STONEX_T02` | `CROP_CLIPPED` | 89.29% | 1 | 0 | 0 | 0 | `ORDER_GOOD` | `CONTEXT_INCOMPLETE` |
| `STONEX_T03` | `CROP_CLIPPED` | 93.89% | 11 | 9 | 2 | 0 | `ORDER_PARTIAL` | `CONTEXT_CONTRADICTORY` |
| `STONEX_T04` | `CROP_CLIPPED` | 100.00% | 10 | 9 | 3 | 0 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |
| `STONEX_T05` | `CROP_CLIPPED` | 100.00% | 9 | 3 | 0 | 0 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |
| `TRADEWEB_T01` | `CROP_CLEAN` | 100.00% | 0 | 0 | 0 | 0 | `ORDER_GOOD` | `CONTEXT_CLEAN_BUT_UNHELPFUL` |
| `TRADEWEB_T02` | `CROP_CLEAN` | 83.33% | 12 | 10 | 0 | 6 | `ORDER_PARTIAL` | `CONTEXT_CONTRADICTORY` |
| `TRADEWEB_T03` | `CROP_CLEAN` | 85.48% | 18 | 20 | 0 | 9 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |
| `TRADEWEB_T04` | `CROP_CLEAN` | 100.00% | 0 | 0 | 0 | 0 | `ORDER_GOOD` | `CONTEXT_CLEAN_BUT_UNHELPFUL` |
| `TRADEWEB_T05` | `CROP_CLIPPED` | 87.84% | 18 | 18 | 0 | 9 | `ORDER_GOOD` | `CONTEXT_CONTRADICTORY` |

## Token load и truncation

Все доступные total input/output usage взяты из provider receipts. Actual source-package load получен парной разностью Arm B − Arm A; component split prompt/source/schema приведён как offline o200k estimate только там, где receipt не дал модальности. Truncation: `0`; observed context-limit errors: `0`; max output budget: `8192`.

| Model | Actual usage | Max input | Max output | Avg source share | Cost delta USD | Latency delta s | Truncated |
|---|---:|---:|---:|---:|---:|---:|---:|
| `anthropic_haiku` | 24/24 | 3763 | 1407 | 26.71% | 0.017204 | -41.667 | 0 |
| `anthropic_opus` | 22/24 | 6073 | 1690 | 26.75% | 0.107415 | -39.632 | 0 |
| `google_flash_lite` | 24/24 | 3320 | 2060 | 34.24% | 0.006273 | -56.901 | 0 |
| `openai_mini` | 24/24 | 4658 | 1232 | 26.43% | 0.009112 | -43.091 | 0 |

## Context versus result

Context classes: `{"CONTEXT_CLEAN_BUT_UNHELPFUL": 5, "CONTEXT_CONTRADICTORY": 17, "CONTEXT_INCOMPLETE": 2}`. В каждой группе сохранены paired Arm B − Arm A deltas по recall, unsupported values, row/column association, header и exact result. Это диагностическая связь, не причинное доказательство.

## Решение

DOC15 не достиг критерия честности: `5/24`, требуется минимум `20/24`. Качество: `INSUFFICIENT`. Нельзя честно закрыть гипотезу через RETIRE или рекомендовать routing. `Do not route or activate source text; first decide whether a separately authorized crop/source-package cleanup goal is worth one narrow retest.`

## Анализ минимальных улучшений

| Problem | Evidence | Minimal correction | Expected benefit | Risk | New calls | Recommendation |
|---|---|---|---|---|---|---|
| `crop_boundary_quality` | `{"nonclean_crops_total": 12, "status_counts": {"CROP_CLEAN": 12, "CROP_CLIPPED": 7, "CROP_CONTAMINATED": 5}}` | Tighten only the target crop margin and exclude footer or neighbor-table regions; preserve frozen DOC15 artifacts unchanged. | Reduce missing headers/edge text and foreign lexical fragments. | A tighter margin can remove legitimate notes or edge values. | `NO_FOR_CORRECTION_YES_FOR_ANY_FUTURE_RETEST` | `CONSIDER_ONLY_IN_SEPARATE_FROZEN_GOAL` |
| `source_text_below_99_percent_critical_coverage` | `{"packages_total": 12}` | Do not pass source text for a package whose measured critical-value coverage is below 99 percent. | Avoid encouraging reliance on incomplete lexical context. | Coverage cannot be known online without a deterministic non-gold proxy. | `NO_FOR_POLICY_RESEARCH_YES_FOR_ANY_FUTURE_RETEST` | `RESEARCH_ONLY_NOT_PRODUCT_ROUTING` |
| `foreign_target_external_fragments` | `{"packages_with_foreign_fragments_total": 16}` | Remove only proven footer, page-header, neighbor-table, and outside-target fragments before a future freeze. | Lower contradictory lexical evidence and token load. | An overbroad filter can delete legitimate table notes. | `NO_FOR_CORRECTION_YES_FOR_ANY_FUTURE_RETEST` | `CONSIDER_ONLY_WITH_EXACT_PRIVATE_DIFF` |
| `proven_critical_duplicates` | `{"packages_total": 5}` | Remove only exact proven duplicate occurrences; retain legitimate repeated values. | Avoid false emphasis without inventing structure. | Repeated values can be legitimate in distinct rows or columns. | `NO_FOR_CORRECTION_YES_FOR_ANY_FUTURE_RETEST` | `CONSIDER_ONLY_IF_EXACT_DUPLICATE_PROOF_EXISTS` |
| `fragment_delimiting` | `{"explicit_start_end_delimiters_present": true, "one_fragment_per_line_present": true}` | None; DOC15 already used explicit start/end delimiters and one fragment per line. | No evidenced benefit from changing delimiters in DOC16. | Changing prompt packaging would create a new arm. | `YES_TO_TEST_ANY_CHANGE` | `NO_CHANGE` |

## Stop boundary

Новых LLM-вызовов, parser/renderer/client/context-builder изменений, исправления frozen artifacts, активации product pipeline, DOC6 или Gate 2 нет.
