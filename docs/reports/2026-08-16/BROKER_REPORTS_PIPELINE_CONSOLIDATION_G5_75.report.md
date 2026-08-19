# G5.75 — Pipeline Consolidation Before End-to-End Replay

Дата: 2026-08-16

Статус: **PARTIAL — нормативный финансовый pipeline консолидирован; общий metadata-region selector отсутствует**

## Результат

Финансовый source pipeline уже имеет один нормативный маршрут и не потребовал рефакторинга:

```text
PDF -> Gate 1 -> CanonicalArtifactV1 -> Adaptive Context
    -> Gate3ChunkBatchLabelingFactory.create
    -> Gate4FinancialCaseRuntimeFactory.create
    -> Gate 5
```

Для visual metadata зафиксирован один supporting candidate:

```text
broker-neutral visual region
    -> existing VLM owner
    -> faithful neutral Markdown
    -> Gate3LlmMetadataAdapterFactory.create
    -> best-effort supporting metadata
```

Этот кандидат не активирован в product. Maintained visual infrastructure умеет искать и рендерить таблицы, но detector имеет задачу `detect_table_regions_only` и прямо исключает document identity header. Общего broker-neutral metadata-region selector в repository нет. Manual crop из G5.70/G5.72 остаётся research evidence; broker/page/percentage hack не добавлялся.

## Authority map

| Смысл | Owner / entrypoint | Статус |
| --- | --- | --- |
| Financial product execution | `NdflWorkflowFactory.create().run_product_path` | PRODUCT/NORMATIVE |
| Financial semantic extraction | `Gate3ChunkBatchLabelingFactory.create` | PRODUCT/NORMATIVE |
| Financial fact materialization/read | `Gate4FinancialCaseRuntimeFactory.create` | PRODUCT/NORMATIVE |
| Visual table route | `PdfDualVlmRuntimeFactory.create_for_openwebui` | PRODUCT/NORMATIVE, table-only |
| Table region selection | `PdfTableIntakeRuntimeFactory.create_for_openwebui` | SUPPORTING, table-only |
| Shared visual provider transport | `PdfGridExperimentProviderFactory.create_for_openwebui` | LEGACY COMPATIBILITY naming; not semantic authority |
| Metadata semantic proposal | `Gate3LlmMetadataAdapterFactory.create` | SUPPORTING / BEST-EFFORT |
| Supporting metadata publication/read | `Gate3MetadataSourceFactRuntimeFactory.create` | SUPPORTING |
| Gate 1 passport | existing optional stage | LEGACY COMPATIBILITY; not G5.60/tax authority |
| G5.61–G5.73 scripts | live/qualification harnesses | PROOF/RESEARCH ONLY |

Research files сохранены как evidence. Product modules не импортируют и не выбирают их как factory default.

## Frozen laws

1. Low-criticality metadata не управляет admission финансовых фактов.
2. Metadata adapter не является tax authority.
3. Gate 4 не зависит от metadata classifier output.
4. G5.61–G5.73 live/benchmark harnesses недоступны из normative runtime.
5. Visual transcription возвращает только neutral Markdown и не назначает machine metadata roles.

Эти законы закреплены в `tests/test_g575_source_pipeline_consolidation.py`. Behavioral Guard A также остаётся покрыт G5.74 counterfactual: wrong/missing/conflicting supporting metadata не меняет financial fingerprint.

## Cold-agent A/B/C

Чистый агент получил только три вопроса и maintained repository surfaces; история и dated research reports ему не передавались.

| Вопрос | Ответ cold agent | Результат |
| --- | --- | --- |
| Financial fact из broker PDF | `Canonical -> Gate 3 -> Gate 4` | PASS |
| Визуальная шапка | region -> existing VLM -> faithful Markdown -> metadata adapter; без общего selector остановиться | PASS |
| Account metadata mismatch | `NO`, financial facts не удалять | PASS |

Primary authority был выбран правильно: `BROKER_REPORTS_PIPELINE_GATES.v1.md`.

## Canary evidence

### Financial

- Factory route: `Gate4FinancialCaseRuntimeFactory.create.rebuild_case`.
- Holdout A: 39 -> 39; exact frozen SHA-256 equality.
- Holdout B: 129 -> 129; exact frozen SHA-256 equality.
- Source stores unchanged: true.

Переиспользован неизменённый G5.69 verifier, поэтому внутренний goal/schema его safe result остаётся G5.69. В G5.75 это только regression evidence.

### Visual Markdown

Повторно проверены три frozen G5.72 cases (`case_b`, `case_f`, `case_c`):

- crop hashes unchanged: true;
- transcription result связан с human audit точным SHA-256: true;
- qualified: 3/3;
- lost source text: 0;
- invented text: 0;
- semantic rewrites: 0;
- metadata roles visible to transcriber: false;
- response fields: только `schema_version`, `markdown`.

Нового model call и выбора лучшего результата не было. Это canary существующего frozen evidence, а не новая модельная квалификация.

Frozen G5.72 Markdown -> semantic-adapter replay также остаётся технически полным: 3 single-shot submissions, retries/voting/best-of-N = 0, contract-invalid = 0. Результат намеренно не переоценён: 7 correct, 2 missed и 1 wrong value boundary. Это подтверждает рабочий supporting seam и одновременно его статус BEST-EFFORT, а не financial/tax authority.

## Проверки

- G5.75 guards: `6 passed in 4.35s`.
- Consolidated source/architecture suite: `137 passed in 73.34s`; failures = 0, только существующие deprecation warnings.
- Ruff check/format check: passed.
- Closed-world: runtime imports/build/package/env не менялись; product import scan G5.61–G5.73 harnesses = 0.
- Product/runtime modules changed by G5.75: 0.

## Изменения и KISS

- Обновлена одна текущая navigation authority: `BROKER_REPORTS_PIPELINE_GATES.v1.md`.
- Добавлен один executable guard test.
- Добавлены report, safe receipt и private evidence receipts.
- General cleanup, rename, provider framework, metadata ontology, semantic tuning, Gate 3/4/5 semantics: 0.
- Broker-specific rules и regex/synonym growth: 0.
- Product activation: 0.

## Terminal

```text
SOURCE_PIPELINE_CONSOLIDATION_PARTIAL
METADATA_VISUAL_SEMANTIC_PATH_PROVEN
METADATA_REGION_SELECTION_GENERALIZATION_GAP_LOCALIZED
NO_BROKER_SPECIFIC_REGION_HACK_ADDED
FINANCIAL_GENERALIZATION_PRESERVED
```

G5.75 на этом останавливается. Visual metadata candidate не должен активироваться до отдельного доказательства broker-neutral region selection. Дальнейшее улучшение ingestion внутри этого GOAL запрещено; следующий разрешённый большой GOAL остаётся full current-case end-to-end replay с текущими нормативными owners.
