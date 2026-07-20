# Broker Reports — Gate 1 и visual phase-performance

Дата: 2026-07-20

Статус: `PHASE_ATTRIBUTED`.

## Executive result

Полный actual-corpus Gate 1 proof прошёл за 1295.886 с; normalization заняла
1167.199 с, peak RSS — 7.045 GB. Предыдущие 1190/1374 с и 7.434 GB находятся в
том же operational envelope. Основные причины не связаны с upload I/O:

1. full-source PDF build — 552.621 с;
2. projection двух крупных CSV — 429.910 с;
3. post-parse domain ingestion + artifact validation — 70.790 с;
4. proof persistence/reload/operator review — 128.210 с после normalization.

Visual recovery прошёл за 530.582 с, peak RSS — 4.120 GB. Из них 461.093 с
(86.9%) заняли 18 isolated two-pass OCR subprocesses; integrated Gate 2 handoff —
59.292 с. Grid/layout и canonical validation вместе занимают единицы секунд.

## Gate 1: фактическая фазовая карта

Inclusive значения вложенных функций не суммируются. В частности, pypdf,
pdfplumber и render входят в `full_source_build.pdf`.

| Фаза | Calls | Inclusive wall | Max call |
|---|---:|---:|---:|
| Full-source PDF build | 50 | 552.620891 с | 54.808018 с |
| CSV table projection | 2 | 429.910332 с | 248.311203 с |
| PDF layout parse (внутри PDF build) | 50 | 298.667163 с | 21.035095 с |
| PDF text-layer parse (внутри PDF build) | 50 | 152.773792 с | 25.992753 с |
| Domain ingestion | 1 | 47.339172 с | 47.339172 с |
| Artifact validation | 1 | 23.450368 с | 23.450368 с |
| XML table projection | 24 | 9.278376 с | 2.284330 с |
| PDF page render/materialization | 22 | 7.148804 / 7.249301 с | 2.31 с |
| PDF table projection | 50 | 3.828653 с | 3.345620 с |
| CSV full-source parse | 2 | 0.817426 с | 0.441075 с |
| XML full-source parse | 24 | 0.527419 с | 0.047351 с |
| HTML full-source parse | 4 | 0.115877 с | 0.033676 с |
| Source byte reads всех форматов | 104 | <0.014 с | <0.001 с |

Форматный corpus: 2 CSV, 50 PDF, 24 ZIP containers, 4 HTML и 24 promoted XML.
ZIP expansion заняла 0.025 с, а значит архивный lineage не является runtime
bottleneck. Два CSV содержат суммарно 2597 rows и 27,241 cells; их projection
стоимость непропорциональна raw parsing и указывает на per-cell provenance,
deep-copy/checksum и validation amplification.

## Actual proof overhead

| Фаза после normalization | Wall |
|---|---:|
| ArtifactStore persistence | 42.826203 с |
| Private artifact reload через resolver | 20.859482 с |
| Actual-corpus operator review | 64.524225 с |
| Public handoff audit | 0.016717 с |

Эти значения почти полностью объясняют разницу между 1167.199-секундной
normalization и 1295.886-секундным proof. Следовательно, прежнее число ~1374 с
нельзя считать чистой product normalization latency: оно включает обязательное
доказательство, повторную загрузку и review.

## Почему требуется около 7 GB RAM

Persisted graph содержит 1531 record и 1.462961 GB JSON payload bytes:

| Artifact class | Records | Payload bytes |
|---|---:|---:|
| Private normalized source payload | 162 | 1,221,494,446 |
| Private normalized source unit | 934 | 149,431,937 |
| Normalized table projection | 259 | 76,319,687 |
| Private normalized text slice | 49 | 13,123,966 |
| Остальные records | 127 | ~2.59 MB |

Peak 7.045 GB — примерно 4.8× persisted JSON. Это объясняется одновременно
живущими Python object graphs для payloads, units, projections и safe/domain
representations; base64 visual page units; повторными `copy.deepcopy`; JSON
encoding buffers при persistence; а затем resolver reload и operator review при
ещё живом normalization package. Это data amplification, а не доказанная утечка:
current peak ниже прежних 7.434 GB, terminal proof корректен.

Нельзя просто удалить visual или review memory: это нарушит zero-silent-loss.
Безопасная цель — bounded streaming/lifetime по документу и освобождение уже
sealed render/intermediate graphs после immutable persistence, с проверкой
побитовой эквивалентности конечных artifacts.

## Visual recovery: фактическая фазовая карта

| Фаза | Calls | Inclusive wall |
|---|---:|---:|
| Observation + layout reconstruction | 18 | 461.199209 с |
| Isolated two-pass OCR (вложено) | 18 | 461.093189 с |
| Integrated Gate 2 handoff | 1 | 59.291924 с |
| Resolver reads | 1231 | 20.972227 с |
| Persist visual results | 1 | 3.254221 с |
| Clone actual ArtifactStore | 1 | 2.197680 с |
| Orientation search | 8 | 1.574494 с |
| Grid detection | 36 | 1.420993 с |
| Image decode | 20 | 0.354188 с |
| Canonical recovery/validation | 36 | 0.234237 с |
| Operator-review object build | 18 | 0.012123 с |

Каждый crop создаёт новый isolated process и заново загружает три PaddleOCR model.
Изоляция корректно ограничивает native lifecycle, но 18 model initializations —
главный measured overhead. Узкая безопасная оптимизация: отдельный OCR worker
process с bounded job count/RSS, immutable model set и hard cleanup между cases.
Двухпроходный OCR, canonical replay и operator authority должны сохраниться.

Terminal visual outcome неизменен: 10/10 recoverable scopes accepted, 1 confirmed
empty, 0 unresolved, 0 unsupported, 17 tables/623 cells, Gate 2 errors 0,
provider calls 0, golden store unchanged.

## Гипотезы

- Rejected: source-byte discovery является причиной 20 минут — <0.014 с.
- Rejected: ZIP expansion является причиной — 0.025 с.
- Rejected: page rendering само по себе является причиной — ~7.15 с.
- Confirmed: PDF parsing/layout и крупный CSV projection — основные Gate 1 CPU
  costs.
- Confirmed: repeated isolated OCR model initialization — основной visual cost.
- Confirmed: proof/review добавляет ~128 с поверх normalization.
- Confirmed: large retained object graph объясняет memory envelope; утечка не
  доказана.

Machine-readable evidence:

- `BROKER_REPORTS_GATE1_ACTUAL_PHASE_PROFILE.v1.safe.json`;
- `BROKER_REPORTS_VISUAL_ACTUAL_PHASE_PROFILE.v1.safe.json`.
