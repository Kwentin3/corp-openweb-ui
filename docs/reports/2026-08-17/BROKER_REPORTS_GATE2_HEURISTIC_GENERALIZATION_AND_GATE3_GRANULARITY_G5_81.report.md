# G5.81 — Gate 2 Heuristic Generalization + Gate 3 Minimal Fail-Closed Granularity

Дата проверки: 2026-08-17

Статус: **остановлено после Part A по предусмотренному stop-contract**

## Итог

```text
GATE2_TABLE_HEURISTIC_FALSE_POSITIVE_BOUNDARY_PROVEN
```

Правило G5.80 сформулировано document-neutral:

```text
OLD: reject when min(row_cell_counts) < 2
NEW: reject when max(row_cell_counts) < 2
OWNER: NormalizedTableProjectionFactory.create / _pdf_geometry_reasons
INPUT: row ordinals already present in candidate cell_inventory
```

В нём нет broker/page/coordinate/financial branches. Однако широкая свежая проверка показала, что правило пока слишком permissive. Поэтому оно не квалифицировано как general law, дополнительный product patch не делался, а Part B не начиналась.

## Свежий machine rebuild

Через существующие owners `FullSourceArtifactFactory.create` и `NormalizedTableProjectionFactory.create` прогнаны четыре реальные PDF:

| Метрика | Результат |
| --- | ---: |
| документов | 4 |
| страниц | 103 |
| table candidates | 90 |
| current ready | 89 |
| current blocked | 1 |
| candidates, повышенных только новым правилом | 79 |
| страниц, затронутых новым правилом | 69 |

Первичная v1-квитанция ошибочно называла число затронутых страниц `promoted...total`. Авторитетна v2-квитанция: она отдельно фиксирует `79 candidates` и `69 pages`; исходные артефакты не перезаписывались.

## Visual qualification

Визуальная проверка использовалась только как development/test oracle. Никакие наблюдения не стали production facts.

| Категория | Source глазами | Canonical | Итог |
| --- | --- | --- | --- |
| known failures, pages 16/19/24/25/26/27 | 6/6 TABLE | 6/6 TABLE | исправлены |
| holdout pages 1–5 | TABLE | 9 старых ready сохранены; ещё 5 повышены новым правилом | positive control пройден |
| large source pages 64–65 | NOT TABLE, prose/legal notes | TABLE | 2 новых false positives |
| holdout page 6 | NOT TABLE, prose/footnotes | TABLE | старый независимый false positive |
| Fidelity pages 10/26/27/28 | NOT TABLE, two-column prose | TEXT | 4 correct negatives |
| TBank page 4 | NOT TABLE | TEXT | 1 correct negative |

### First divergence новых false positives

Обе страницы 64–65 получили `ruled_lines_v0` candidates только из-за rectangle-like line geometry:

| Page | Rows / cells | Vertical vector lines | Rect evidence | Новый rule |
| ---: | ---: | ---: | ---: | --- |
| 64 | 23 / 42 | 0 | 43 | accepted |
| 65 | 10 / 17 | 0 | 18 | accepted |

На визуально настоящих `ruled_lines_v0` таблицах того же корпуса присутствуют десятки или сотни vertical vector lines. Это даёт общий structural candidate-condition:

> При relaxed admission `ruled_lines_v0` требовать реальное column-boundary evidence, а не только прямоугольники строк текста.

Это пока наблюдение, а не доказанный новый закон. Оно **не реализовано**: для честной квалификации нужен отдельный positive/negative corpus, особенно реальные двухколоночные и border-light таблицы. Подбирать threshold по двум страницам запрещено.

### Независимый старый boundary

Holdout page 6 является обычным текстом, но текущий `aligned_text_v0` построил 39 × 11 candidate, проходящий и старое, и новое правило. Это не регрессия `min→max`, но означает, что Gate 2 в целом также требует отдельной проверки aligned-text admission. Исправлять её внутри G5.81 было бы расширением scope.

## Почему Part B не выполнена

Контракт G5.81 прямо требует STOP, если Gate 2 heuristic слишком широка. Поэтому пять Gate 3 incidents не переаудировались и failure-propagation contract не менялся. Это сохраняет порядок доказательства: сначала безопасный Canonical, затем Gate 3 granularity.

Подтверждено:

```text
Gate 3 provider calls = 0
prompt/model/retry/best-of-N changes = 0
validator changes = 0
decimal changes = 0
methodology changes = 0
metadata/VLM product changes = 0
manual facts = 0
production visual dependency = 0
```

## Артефакты

- Machine inventory v2: `docs/reports/2026-08-16/BROKER_REPORTS_GATE2_HEURISTIC_GENERALIZATION_G5_81.machine.v2.safe.json`.
- Safe boundary receipt: `docs/reports/2026-08-17/BROKER_REPORTS_GATE2_HEURISTIC_FALSE_POSITIVE_BOUNDARY_G5_81.machine.safe.json`.
- Audit harness: `services/broker-reports-gate1-proof/scripts/prove_g581_table_heuristic_generalization.py`.
- Private evidence bundle: `broker-reports-g5.81-20260816-v1` under the external private-evidence root (outside Git).
- Private visual truth manifest: `gate2-visual-qualification.private.json` внутри bundle.
- Raw PDFs, contact sheets и page renders: `visual-corpus/` внутри bundle.

## Проверки

```text
ruff audit harness: PASS
py_compile audit harness: PASS
private/safe JSON parse: PASS
focused pytest: 45 passed
```

Тесты: `test_broker_reports_table_projection.py` и `test_g580_atomic_source_facts.py`.

## KISS и следующий допустимый GOAL

G5.81 добавил только воспроизводимый audit harness и evidence/report artifacts. Product runtime, contracts и LLM path не менялись.

Следующий допустимый GOAL — узко доказать general structural admission для двух обнаруженных классов по отдельности:

1. `ruled_lines_v0`: real column-boundary evidence против rectangle-only prose.
2. `aligned_text_v0`: table alignment против multi-column/footnote prose.

Только после зелёного positive + negative holdout можно вернуться к пяти Gate 3 rejections и minimal fail-closed granularity.
