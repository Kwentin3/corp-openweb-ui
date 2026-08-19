# G5.93 — насыщение deterministic PDF parser перед VLM-сравнением

Дата: 2026-08-17
Статус: `PARSER_BASELINE_MATURE`; применён один последний общий structural fix; Variant A заморожен

## Результат

Известный `aligned_text_v0` false positive закрыт в существующем owner
`NormalizedTableProjectionFactory.create / _pdf_geometry_reasons` одним
document-neutral правилом:

> После удаления пустых parser spacer rows один и тот же непустой
> multi-column occupancy pattern должен описывать строгое большинство content
> rows.

Правило не читает текст, имя PDF, broker, page number, абсолютные координаты или
финансовые слова. Новый detector, parser framework, OCR/VLM fallback и
reconciliation layer не созданы.

При fail-closed отклонении projection теперь учитывает только fallback line refs,
которые входят в его selected scope. Внешние page-line refs остаются у
существующих line-cluster owners. Это сохраняет `lost refs = 0`,
`duplicates = 0` и валидный blocked terminal.

## Architecture bootstrap и scope

- Gate 1 владеет custody/routing; Gate 2 Canonical владеет deterministic
  non-financial representation; Gate 3+ владеет финансовой семантикой.
- Sole parser route:
  `FullSourceArtifactFactory.create -> NormalizedTableProjectionFactory.create -> TableProjectionValidator`.
- Нормативны `BROKER_REPORTS_PIPELINE_GATES.v1`,
  `BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0` и
  `BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v2`.
- Maintained change сделан только в существующем projection/admission owner.
  `pdf_layout.py`, `full_source.py`, Gate 3+, Dictionary, Role Pack, methodology,
  provider и VLM/OCR source paths не менялись.
- Visual inspection использовалась только как development oracle. Production
  visual dependency остаётся нулевой.

## First divergence

Original PDF page визуально содержит нумерованную прозу/glossary, а не повторяемые
records `row x column`. Машина построила `39 x 11 TABLE`:

| Structural signal | False prose | Existing true aligned control |
|---|---:|---:|
| Machine rows | 39 | 7 |
| Content rows | 21 | 4 |
| Empty parser spacer rows | 18 | 3 |
| Claimed columns | 11 | 3 |
| Distinct non-empty occupancy patterns | 10 | 1 |
| Dominant pattern rows | 4/21 | 4/4 |
| Strict majority | no | yes |

Первое расхождение находится до финансовой семантики: prose word alignment
породил много несовместимых row shapes, но прежний admission проверял только
минимальную геометрию и exact word ownership.

## Qualification corpus

Fresh replay выполнен через public factory path по тому же визуально
квалифицированному корпусу G5.82. Candidate population сопоставлена с прежней
по устойчивому structural key `source alias + page + line range + strategy`, а
не по scope-dependent refs.

| Проверка | До G5.93 | После G5.93 |
|---|---:|---:|
| Documents / pages | 4 / 103 | 4 / 103 |
| Candidates | 90 | 90 |
| `READY` | 87 | 86 |
| `blocked` | 3 | 4 |
| Status changes | — | 1 |
| New `READY` candidates | — | 0 |
| Visually true promoted tables `READY` | 77/77 | 77/77 |
| Reviewed ruled-prose negatives blocked | 2/2 | 2/2 |
| Known aligned-prose false positive blocked | 0/1 | 1/1 |
| Positive controls `READY` | 10/10 | 10/10 |
| Repaired pages structured | 6/6 | 6/6 |
| Lost/unaccounted ref cases | 0 | 0 |
| Duplicate ref cases | 0 | 0 |
| Validator failures | 0 | 0 |

Девять остальных visual non-table controls по-прежнему не получают candidate
acceptance: detector owner byte-identical, exact 90-candidate keyset не изменился,
а after-ready set является строгим подмножеством before-ready set.

Единственная дельта — прежний `aligned_text_v0` false positive. Он получает
`pdf_table_aligned_text_stable_column_pattern_missing` и возвращается в
line-cluster representation без потери source refs.

## Generality / KISS

- Broker-specific rules: `0`.
- Page-specific rules: `0`.
- Document/PDF-name rules: `0`.
- Financial-semantic parser rules: `0`.
- Text/keyword inspection в новом правиле: `0`.
- Новые strategies/detectors/frameworks: `0`.
- Provider/VLM/OCR calls: `0`.
- Gate 3+ maintained source changes: `0`.

Изменение состоит из одного strategy-local structural predicate и общей
in-scope coverage correction для blocked projections. Это один fix class, а не
новая подсистема.

## Frozen complexity baseline A

Counts намеренно грубые и нужны только для будущего A/B сравнения:

| Показатель | Frozen value |
|---|---:|
| Emitted PDF table strategies | 2 (`ruled_lines_v0`, `aligned_text_v0`) |
| Strategy refs, которые projection умеет распознать | 4 |
| Fail-closed PDF projection rejection classes | 11 |
| Основные fallback terminal families | 3 |
| Named table/parser config thresholds | 14 |
| Local numeric/ratio decision knobs | примерно 23 |
| Общий threshold/ratio order of magnitude | примерно 37 |
| Direct layout/projection tests | 25 |
| Collected tests с inherited backend compatibility | 52 |
| Known frozen structural debt classes | 4 |

Maintained code footprint для прозрачности, не как KPI:

- `pdf_layout.py`: 856 lines;
- `pdf_layout_units.py`: 1297 lines;
- `full_source.py`: 2603 lines (общий multi-format orchestration, не только tables);
- `table_projection.py`: 1565 lines (native formats + PDF projection).

Runtime dependencies Variant A: Python, pinned `pdfplumber 0.11.10`, pinned
`pdfminer.six 20260107` и существующий local PDF/text stack. Network/provider
cost: `0`; VLM/OCR cost: `0`. Fresh qualification replay занял 128.3 секунды
для 103 pages на текущем Windows host (~1.25 s/page); это evidence-run timing,
не production SLA.

## Frozen limitations

1. Геометрически идеально регулярная проза/список может быть неотличима от
   borderless table без semantic или visual evidence. Добавлять text rules в
   Variant A запрещено.
2. В реальном qualified corpus нет положительного `aligned_text_v0` table;
   существующий positive control синтетический. Поэтому real-world recall этого
   strategy не объявляется доказанным.
3. Реальная vertical-only ruled table в доступном corpus отсутствует; поддержка
   симметрична в коде, но visual qualification не заявляется.
4. Scanned, irregular и visually implied tables остаются вне deterministic
   baseline. Они являются предметом comparator Variant B, а не поводом добавлять
   fallback в A.

Эти классы требуют уже непропорционального роста thresholds, semantic rules,
visual/OCR path или отдельной recovery architecture. Поэтому они заморожены как
design limitations, а не открывают G5.93A/G5.93B.

## Verification

```text
Focused layout/projection: 52 passed
Adjacent parser/canonical suite: 294 passed
Ruff: PASS
py_compile: PASS
Full real-PDF replay: PASS (4 documents / 103 pages / 90 candidates)
Exact table_projection source in 3 generated bundles: PASS
Workspace-path import in generated bundles: ABSENT
Other bundle tests: 12 passed, 1 deselected
```

Один общий bundle run дал `94 passed / 1 failed`: stale guard запрещает строку
`gate2_financial_evidence_production_runtime`, уже добавленную в current dirty
bundle generator/architecture policy предыдущими semantic routes. G5.93 этот
module, generator rule и guard не менял; исправлять конфликт означало бы выйти
в Gate 3+/semantic scope. Parser module при этом byte-exact встроен во все три
closed-world bundles, `sys.path.insert` отсутствует. Этот unrelated dirty-tree
verification debt не превращён в parser work.

## Delivery boundary

- Изменения и evidence остаются локальными.
- Commit, push, PR, stage deploy и product activation не выполнялись.
- Private PDFs, crops и exact per-candidate evidence остаются вне Git.
- Safe tracked receipt не содержит customer text или координаты.

## Verdict

```text
PARSER_BASELINE_MATURE
ONE_FINAL_GENERAL_LOW_HANGING_FIX_APPLIED

DETERMINISTIC_PDF_PARSER_SATURATION_PROVEN
GENERAL_STRUCTURAL_LOW_HANGING_FIXES_EXHAUSTED
BROKER_SPECIFIC_HEURISTICS_ZERO
PAGE_SPECIFIC_HEURISTICS_ZERO
PRODUCTION_VISUAL_DEPENDENCY_ZERO
KNOWN_STRUCTURAL_LIMITATIONS_FROZEN
PARSER_COMPLEXITY_BASELINE_FROZEN
VARIANT_A_READY_FOR_FAIR_COMPARISON
NEXT_GOAL=VLM_VS_DETERMINISTIC_PARSER
```

После G5.93 новые parser-improvement GOAL до фиксированного A/B comparator не
открываются.
