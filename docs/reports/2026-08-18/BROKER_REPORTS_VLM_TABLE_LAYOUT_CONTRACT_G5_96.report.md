# Broker Reports G5.96 — VLM Table Layout Contract → Deterministic Materialization

Дата: 2026-08-18

Статус: research-only Gate 2 proof-of-concept

Terminal: `VLM_LAYOUT_CONTRACT_DETERMINISTIC_MATERIALIZATION_PROVEN`

## Вывод

Узкая гипотеза подтверждена на замороженном development corpus G5.95: VLM-контракт без body values задал проверяемую визуальную ось, после чего deterministic resolver переложил только настоящие parser words. Все пять известных ошибочных `13 → 11` column relations исправлены, known-good `5 → 5` сохранена, prose control не материализован.

Это не production hybrid. Routing, reconciliation, fallback cascade и activation не проектировались.

## Architecture bootstrap

- Домен: Gate 2, структурная PDF table projection.
- Нормативные границы: `BROKER_REPORTS_PIPELINE_GATES.v1`, `BROKER_REPORTS_CANONICAL_ARTIFACT.v1`, `BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0`, Gate 2 implementation map.
- Production owners не изменены: `FullSourceArtifactFactory`, `NormalizedTableProjectionFactory.create`, `CanonicalNormalizerFactory.create`.
- POC использует `PdfTextLayerParserFactory.create` и frozen G5.94 Variant A; его результат помечен `research_private_not_published`.
- Новый production schema/parser/store/reader не создан. Gate 3+ не затронут.

## Минимальный layout contract

VLM получает одну уже известную rendered page и может вернуть только:

- локальное disposable name;
- `start_hints.anchor_tokens` и ordinal таблицы относительно anchor;
- `end_hints.boundary`: `next_section`, `footer` или `end_of_page`;
- число визуальных колонок и header rows;
- признаки continuation, repeated/mixed body pattern, wrapped rows и subtotal rows;
- при видимой шапке — короткие header-word hints по колонкам.

Schema не имеет каналов для rows, cells, body values, Canonical IDs, bbox или financial semantics. Числоподобные breadcrumb/header hints отклоняются. В materialization ни одна строка из VLM не становится source literal.

## Детерминированный механизм

1. Breadcrumb разрешается против exact parser line inventory.
2. Между подтверждёнными start/end выбирается один parser table candidate.
3. Header hints разрешаются против exact source words; для continuation переиспользуется уже подтверждённая ось того же source breadcrumb и числа колонок.
4. Parser row bands сохраняются, а source words один раз раскладываются по подтверждённой column axis.
5. Каждое слово сверяется с frozen A literal, word ref и source value ref; identity создаётся только после разрешения source region.

Fail-closed применяется при 0/2+ source regions, неоднозначном breadcrumb, отсутствии проверяемой оси, несовместимых boundaries или неполном source binding.

## Provider evidence

- Исходных страниц: 7.
- Initial submissions: 7.
- Завершённых model outputs: 7.
- Одна initial submission завершилась transport timeout без model output; выполнен один явно записанный transport-recovery call.
- Конкурирующих outputs: 0; best-of-N: 0; hidden retry: 0; provider failover: 0.
- VLM body values used: 0.
- VLM Canonical IDs: 0.
- VLM exact bbox: 0.

На prose control VLM предложила четыре ложных двухколоночных контракта. Resolver отклонил все: независимый headerless contract без source-resolvable или ранее проверенной axis недостаточен, даже если parser также видит широкий geometry candidate. Это обязательный compatibility guard, а не semantic rule.

## Результаты materialization

| Page | Контроль | Parser cols | Result cols | Rows | Source words/refs | Режим |
|---:|---|---:|---:|---:|---:|---|
| 23 | known wrong relation | 13 | 11 | 4 | 21 / 21 | header axis |
| 24 | continuation/subtotal | 13 | 11 | 34 | 353 / 353 | inherited axis |
| 25 | continuation/subtotal | 13 | 11 | 36 | 357 / 357 | inherited axis |
| 26 | continuation/subtotal | 13 | 11 | 36 | 357 / 357 | inherited axis |
| 27 | continuation/subtotal | 13 | 11 | 28 | 271 / 271 | inherited axis |
| 28 | known-good | 5 | 5 | 48 | 312 / 312 | preserved source candidate |
| 64 | ordinary prose | — | — | — | 0 / 0 | fail closed |

Итого: `1,671 / 1,671` materialized parser words имеют source refs; invented source literals = `0`. Для последней subtotal row на p027 непустые source cells оказались в колонках `1, 6, 7, 8, 9, 10`, а не в разреженной последовательности старого 13-column A.

## Complexity delta

Механизм состоит из четырёх операций: resolve breadcrumbs → select one source region → derive/reuse axis → rebin exact words.

- document-specific code branches: 0;
- body-value heuristic rules: 0;
- financial-semantic rules: 0;
- production owner changes: 0;
- deterministic mechanism: 10 функций, 407 строк с source binding и fail-closed validation;
- весь research harness: 1,563 строки, включая provider transport, strict schema validation, private/safe evidence и CLI.

Вердикт по сложности положительный, но узкий: сама table reconstruction сведена к bounded axis assignment и не потребовала нового parser framework. Общий harness не мал, потому что включает transport и доказательную обвязку; переносить его целиком в production нельзя.

Selected-page replay использует lossless single-page slice исходного PDF, затем публичный `PdfTextLayerParserFactory.create`; каждое слово повторно сверяется с frozen full-document A literal/ref. Финальный deterministic replay занял 4.5 секунды и не делал provider calls.

## Проверки

```text
76 passed, 5 warnings in 3.97s
```

Покрыты G5.96 behavioral tests, frozen G5.94/G5.95 harnesses, PDF layout owner и normalized table projection owner. Warnings — существующие SWIG deprecation warnings.

## Evidence и границы

- [Frozen manifest](../../../services/broker-reports-gate1-proof/benchmarks/table_layout_contract_g596/manifest.json)
- [Recovered contract safe evidence](BROKER_REPORTS_VLM_TABLE_LAYOUT_CONTRACT_G5_96.contract.recovered.safe.json)
- [Final materialization safe evidence](BROKER_REPORTS_VLM_TABLE_LAYOUT_CONTRACT_G5_96.materialization.v4.safe.json)

Private page bytes, breadcrumbs, provider payloads, literals, coordinates и materialized cells остаются вне Git. Safe artifacts содержат только counts, hashes, statuses и агрегаты.

G5.96 не разрешает следующий шаг автоматически. Возможный следующий отдельный GOAL — frozen unseen holdout/repeatability layout-contract qualification. Production routing или activation для этого не разрешены.
