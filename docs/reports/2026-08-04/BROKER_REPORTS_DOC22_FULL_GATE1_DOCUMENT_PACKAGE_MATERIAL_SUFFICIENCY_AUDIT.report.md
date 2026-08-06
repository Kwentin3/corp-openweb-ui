# DOC22 — Full Gate 1 Document Package Material Sufficiency Audit

Дата: 2026-08-04  
Тип: research-first; без Gate 3, нового parser/cropper/product route.

## Итог

```text
DOC22_RESEARCH = COMPLETED
FULL_GATE1_DOCUMENT_SUFFICIENCY = CONFIRMED
PARSER_CONTEXT_RESCUE = SUBSTANTIAL
BEST_GATE1_DOCUMENT_PACKAGE = RESEARCH_SHADOW_ALL_PARSER_LINES_PAGE_AND_BLOCK_BOUNDARIES_PLUS_EXISTING_TARGET_TABLE_JSON
AUTOMATED_AUDIT = BLOCKED
CROP_RESEARCH_POLICY = DEFINE_MINIMUM_DOCUMENT_CONTEXT_CONTRACT
```

`CONFIRMED` относится к research-only shadow package, а не к активному product handoff. Автоматизация не валидирована: exact preflight прошёл, но frozen run завершил 23/48 cases и получил HTTP 429 в остальных 25; retry/fallback/repair не применялись.

## 1. Фактический Gate 1 handoff

Текущая карта:

```text
PDF
→ Gate1Normalizer
→ FullSourceArtifactFactory
→ PdfLayoutUnitBuilder: page-local table units, затем line units
+ NormalizedTableProjectionFactory
→ gate2_handoff_v0: bundle ссылок на source units/table projections
→ следующий этап читает отдельные units
```

Единого ordered full-document payload в реальном downstream handoff нет. `ManagedPdfDocument`/v2 остаются inactive research routes. Поэтому создан только research shadow: все 6 документов, все страницы, все существующие parser lines в существующем порядке, block/page boundaries и точная привязка к существующему table JSON. Новых headings/classes/relations, исправленного текста и перечитанных PDF-значений нет.

Кодовые опоры: `normalizer.py:130,137,550-563`; `pdf_layout_units.py:795`; `gate2_handoff.py:1051,1123`; `managed_pdf_document.py:58`; `managed_pdf_document_v2.py:33-38,191-192`.

## 2. Метод фазы A

Для каждого из 48 cases агент непосредственно сопоставил исходный PDF, полную страницу, overlay, полный shadow document package, конкретный table JSON и соседние parser blocks. Проверены все 15 обязательных категорий. Исключённых cases: 0. Новых provider calls в фазе A: 0.

Запрет ложного rescue применён буквально: общая встречаемость даты/масштаба в документе не считалась связью. Нужна непосредственная page/order/continuation привязка.

## 3. Прямая достаточность

| Provider | Document sufficient | Rescued | Critical | Ambiguous | Material | Phase B eligible |
|---|---:|---:|---:|---:|---:|---|
| Google Flash Lite | 1 | 21 | 0 | 2 | 22/24 | PASS |
| Anthropic Opus | 4 | 19 | 0 | 1 | 23/24 | PASS |

Из 43 isolated-table `CRITICAL_LOSS` cases 40 однозначно спасены документным контекстом; 3 остались ambiguous; document-wide critical loss не осталось.

Главный повторяемый механизм — parser text непосредственно перед/после target и repeated page headers. Это не казуальное правило для обрезанной строки.

## 4. Потери, rescue и конфликты по case

| Table | Provider | Crop | Isolated | Document | Rescued categories | Remaining | Conflicts |
|---|---|---|---|---|---|---|---|
| ACORNS_T01 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, CURRENCY | — | NO_CONFLICT |
| ACORNS_T01 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD | — | NO_CONFLICT |
| ACORNS_T02 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | AMBIGUOUS | TABLE_SCOPE, PERIOD | ROW_RELATION, UNSUPPORTED_VALUE | CONTEXT_CONFLICT |
| ACORNS_T02 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD | — | NO_CONFLICT |
| ACORNS_T03 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD | — | NO_CONFLICT |
| ACORNS_T03 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD | — | NO_CONFLICT |
| JEFFERIES_T01 | google_flash_lite | CROP_CONTAMINATED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE | — | NO_CONFLICT |
| JEFFERIES_T01 | anthropic_opus | CROP_CONTAMINATED | NONCRITICAL_LOSS | DOCUMENT_SUFFICIENT | — | — | NO_CONFLICT |
| JEFFERIES_T02 | google_flash_lite | CROP_CONTAMINATED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE | — | NO_CONFLICT |
| JEFFERIES_T02 | anthropic_opus | CROP_CONTAMINATED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE | — | NO_CONFLICT |
| JEFFERIES_T03 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | — | NO_CONFLICT |
| JEFFERIES_T03 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | — | NO_CONFLICT |
| JEFFERIES_T04 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION, CONTINUATION_IDENTITY | — | NO_CONFLICT |
| JEFFERIES_T04 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION, CONTINUATION_IDENTITY | — | NO_CONFLICT |
| JEFFERIES_T05 | google_flash_lite | CROP_CONTAMINATED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, MISSING_VALUE, GROUP_OR_TOTAL_RELATION, CONTINUATION_IDENTITY | — | NO_CONFLICT |
| JEFFERIES_T05 | anthropic_opus | CROP_CONTAMINATED | NONCRITICAL_LOSS | DOCUMENT_SUFFICIENT | — | — | NO_CONFLICT |
| JEFFERIES_T06 | google_flash_lite | CROP_CONTAMINATED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE | — | NO_CONFLICT |
| JEFFERIES_T06 | anthropic_opus | CROP_CONTAMINATED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE | — | NO_CONFLICT |
| LPL_T01 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | AMBIGUOUS | TABLE_SCOPE, PERIOD | AS_OF_VS_YEARS_ENDED | PERIOD_AMBIGUITY |
| LPL_T01 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | AMBIGUOUS | TABLE_SCOPE, PERIOD | AS_OF_VS_YEARS_ENDED | PERIOD_AMBIGUITY |
| LPL_T02 | google_flash_lite | CROP_CONTAMINATED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | UNIT_OR_SCALE | — | NO_CONFLICT |
| LPL_T02 | anthropic_opus | CROP_CONTAMINATED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | UNIT_OR_SCALE | — | CONTEXT_CONFLICT |
| LPL_T03 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | PERIOD, UNIT_OR_SCALE | — | NO_CONFLICT |
| LPL_T03 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | PERIOD, UNIT_OR_SCALE | — | NO_CONFLICT |
| LPL_T04 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, UNIT_OR_SCALE | — | NO_CONFLICT |
| LPL_T04 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, UNIT_OR_SCALE | — | NO_CONFLICT |
| STONEX_T01 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, MISSING_VALUE | — | NO_CONFLICT |
| STONEX_T01 | anthropic_opus | CROP_CLEAN | NONCRITICAL_LOSS | DOCUMENT_SUFFICIENT | — | — | NO_CONFLICT |
| STONEX_T02 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | COLUMN_RELATION | — | NO_CONFLICT |
| STONEX_T02 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | COLUMN_RELATION | — | NO_CONFLICT |
| STONEX_T03 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, COLUMN_RELATION | — | NO_CONFLICT |
| STONEX_T03 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, COLUMN_RELATION | — | NO_CONFLICT |
| STONEX_T04 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | — | NO_CONFLICT |
| STONEX_T04 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION | — | NO_CONFLICT |
| STONEX_T05 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION, CONTINUATION_IDENTITY | — | NO_CONFLICT |
| STONEX_T05 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE, PERIOD, UNIT_OR_SCALE, COLUMN_RELATION, CONTINUATION_IDENTITY | — | NO_CONFLICT |
| TRADEWEB_T01 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE | — | NO_CONFLICT |
| TRADEWEB_T01 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | TABLE_SCOPE | — | NO_CONFLICT |
| TRADEWEB_T02 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | PERIOD, COLUMN_RELATION | — | NO_CONFLICT |
| TRADEWEB_T02 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | PERIOD, COLUMN_RELATION | — | NO_CONFLICT |
| TRADEWEB_T03 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | PERIOD, COLUMN_RELATION | — | NO_CONFLICT |
| TRADEWEB_T03 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | PERIOD, COLUMN_RELATION | — | CONTEXT_CONFLICT |
| TRADEWEB_T04 | google_flash_lite | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | PERIOD, COLUMN_RELATION | — | NO_CONFLICT |
| TRADEWEB_T04 | anthropic_opus | CROP_CLEAN | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | PERIOD, COLUMN_RELATION | — | NO_CONFLICT |
| TRADEWEB_T05 | google_flash_lite | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | PERIOD, COLUMN_RELATION | — | NO_CONFLICT |
| TRADEWEB_T05 | anthropic_opus | CROP_CLIPPED | CRITICAL_LOSS | RESCUED_BY_DOCUMENT_CONTEXT | PERIOD, COLUMN_RELATION | — | NO_CONFLICT |
| OPPENHEIMER_T01 | google_flash_lite | CROP_CLEAN | SUFFICIENT | DOCUMENT_SUFFICIENT | — | — | NO_CONFLICT |
| OPPENHEIMER_T01 | anthropic_opus | CROP_CLEAN | SUFFICIENT | DOCUMENT_SUFFICIENT | — | — | NO_CONFLICT |

## 5. Что восстановил parser context

- `TABLE_SCOPE`, `PERIOD`, `UNIT_OR_SCALE`, `COLUMN_RELATION` чаще всего восстановлены immediate same-page preceding lines/page headings.
- `CONTINUATION_IDENTITY` для Jefferies/StoneX восстановлена repeated heading + previous-page body.
- `MISSING_VALUE`/`GROUP_OR_TOTAL_RELATION` в Jefferies и StoneX восстановлены following blocks в том же parser order.
- Критические примечания/qualifiers, обрезанные из table JSON, доехали в following parser text.

Не восстановлены однозначно:

- `LPL_T01` у обоих providers: общий header `As of and for the Years Ended` не связывает каждую строку со stock/flow basis без доменной интерпретации (`PERIOD_AMBIGUITY`).
- Google `ACORNS_T02`: table JSON дублирует split label как две строки, parser text показывает split line/value, но shadow не назначает один output authority (`CONTEXT_CONFLICT`).

Дополнительные, но не блокирующие конфликты: Opus `LPL_T02` присоединил heading следующей таблицы; Opus `TRADEWEB_T03` вынес currency marker в extra cell. Existing parser order позволяет сохранить материальный смысл, но конфликты явно записаны.

## 6. Crop-class effect

| Crop class | Google | Opus | Document critical |
|---|---|---|---:|
| Clean (12) | 1 sufficient / 9 rescued / 2 ambiguous | 2 sufficient / 9 rescued / 1 ambiguous | 0 |
| Clipped (7) | 7 rescued | 7 rescued | 0 |
| Contaminated (5) | 5 rescued | 2 sufficient / 3 rescued | 0 |

Все clipped/contaminated cases стали materially sufficient на уровне документа; все три ambiguous cases относятся к clean crops. Следовательно, DOC22 не подтверждает crop quality как определяющую причину document-package sufficiency.

## 7. Phase B exact qualification

- Model: exact `gpt-5.6-sol`.
- Route: existing research `NativePdfTransport.invoke_image_structured → _post_plain → OpenAI Responses API`.
- HTTP 200; image input + complete 181-page verifier projection + strict structured output.
- Qualification input: 235290 tokens при documented context window 1050000.
- `temperature`: omitted; `reasoning.effort=low`; max output 2048.
- Product Gate1 adapter не менялся: он hardcodes `temperature=0`; его изменение нарушило бы `GATE1_CHANGED=FALSE`.

## 8. Automated audit

```text
EXPECTED = 48
STARTED = 48
COMPLETED = 23
FAILED_HTTP_429 = 25
RETRY = 0
FALLBACK = 0
REPAIR = 0
UNACCOUNTED = 0
```

Наблюдаемое agreement на 23 completed cases: 20/23 (87.0%); rescue agreement 18/18; ambiguity agreement 0/3. Verifier трижды превратил direct `AMBIGUOUS` в safe verdict и не увидел конфликт. `FALSE_SAFE_TOTAL` по узкому контрактному определению (direct critical → automated safe) равен 0, потому что direct critical cases отсутствуют; это не отменяет трёх ambiguity misses.

Из-за 25 rate-limited slots corpus agreement не вычислен и `AUTOMATED_AUDIT=BLOCKED`, а не `VALIDATED`.

## 9. Решение

Дальнейший crop research приостанавливается как основной маршрут. Следующий разумный research goal — определить минимальный document-context contract на общих повторяемых элементах: complete page/parser order, adjacent text, page/section identity, period/scale headers, continuation boundary и provenance. DOC22 не активирует такой product contract и не проектирует Gate 3.

## 10. Acceptance

```text
GATE1_DOCUMENT_HANDOFF_AUDITED = TRUE
RESEARCH_SHADOW_PACKAGE_CREATED_IF_NEEDED = TRUE
NEW_PRODUCT_HANDOFF_CONTRACT_CREATED = FALSE
TABLES_TOTAL = 24
GATE1_TABLE_ARTIFACTS_PER_TABLE = 2
DIRECT_CASES_TOTAL = 48
DIRECT_AGENT_REVIEW_COMPLETED = TRUE
FAILED_CASES_EXCLUDED = 0
ISOLATED_VS_DOCUMENT_VERDICTS_REPORTED = TRUE
RESCUED_CONTEXT_REPORTED = TRUE
RESCUE_SOURCES_REPORTED = TRUE
REMAINING_CRITICAL_LOSSES_REPORTED = TRUE
CONFLICTS_REPORTED = TRUE
PROVIDER_COMPARISON_REPORTED = TRUE
CROP_CLASS_EFFECT_REPORTED = TRUE
AUTOMATION_ELIGIBILITY_REPORTED = TRUE
EXACT_ADAPTER_PREFLIGHT_PASSED = TRUE
AUTOMATED_CASES_TOTAL = 48
ALL_AUTOMATED_CALLS_ACCOUNTED = TRUE
RETRY_TOTAL = 0
FALSE_SAFE_TOTAL_REPORTED = TRUE
GATE1_CHANGED = FALSE
CROPPER_CHANGED = FALSE
GATE2_CHANGED = FALSE
GATE3_CREATED = FALSE
PRODUCT_PIPELINE_ACTIVATED = FALSE
```
