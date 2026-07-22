# Broker Reports — Goal 1: representation identity и context selection

Дата: 2026-07-22

Статус: `NOT_CLOSED`

## Вывод

Текущий released contour сохраняет provenance и детерминированно материализует semantic visual table, но не имеет отдельной поддерживаемой границы сборки контекста для обычного answering LLM. Поэтому фактический final answer-context payload для трёх контрольных метрик отсутствует, а инварианты «одна interpretation-bearing representation на source scope» и «нулевое дублирование» не могут считаться доказанными.

Это не дефект semantic JSON и не повод менять VLM prompt. Разрыв находится после Gate 2: между сохранёнными представлениями/фактами и native OpenWebUI answer completion.

## Измеренное evidence

- Repository revision и live stage совпадают: `4f7551f07f09ecec95030e5e0eadb771ed680d65`.
- Все три live Function bundles и 12 managed extraction prompts прошли exact parity readback.
- На stage обнаружено пять Broker Reports Functions: private intake, Normalizer Action, Gate 1 Pipe и два Gate 2 Pipe. Answer-context Function среди них отсутствует.
- Answer-oriented managed prompt отсутствует: `0` из `12`.
- Final answer-context payloads для контрольного вектора: `0`.
- Явные `evidence_group/source_scope` поля на semantic-to-answer boundary: `0`.
- Явные interpretation roles на той же boundary: `0`.
- Приватный expected-value reference не читался и не передавался runtime.

## Где именно разрывается контракт

1. Semantic materialization сохраняет `source_document_ref` и upstream `candidate_ref`, то есть derivation lineage существует и его можно переиспользовать. Но projection не назначает evidence-group identity или interpretation role.
2. Gate 2 table package сохраняет `upstream_source_representation = semantic_visual_logical_table`, однако это provenance descriptor, а не правило выбора среди параллельных представлений.
3. Released migration намеренно добавляет semantic package рядом с maintained full-source units. Это сохраняет исходник, но само по себе не определяет, какой из двух носителей должен интерпретироваться как финансовый факт.
4. Gate 1 Pipe завершает работу compact processing report; Gate 2 Pipe — compact extraction summary. Ни один из них не формирует payload для последующего пользовательского вопроса.
5. Следовательно, перечислить «все представления, реально дошедшие до answering model» для каждой из трёх метрик невозможно: answering-model handoff ещё не существует.

Кодовые точки аудита:

- `semantic_visual_table_materialization.py:625` — Gate 2 projection и существующая lineage;
- `gate2_table_packages.py:244` — самостоятельный semantic package;
- `gate2_table_packages.py:463` — semantic provenance descriptor;
- `broker_reports_gate1_pipe.py:606` — terminal compact Gate 1 chat content;
- `broker_reports_gate2_source_fact_pipe.py:244` — terminal compact Gate 2 summary;
- `test_broker_reports_semantic_visual_table_downstream.py:18` — интеграционный контракт «semantic package добавлен, full source сохранён».

## Acceptance status

| Инвариант | Статус | Измерение |
|---|---|---:|
| `SOURCE_SCOPE_GROUPING` | `NOT_CLOSED` | explicit groups: `0` |
| `INTERPRETATION_BEARING_REPRESENTATIONS` | `NOT_CLOSED` | explicit roles: `0` |
| `PROVENANCE_ONLY_REPRESENTATIONS` | `NOT_CLOSED` | selection rule отсутствует |
| `SEMANTIC_DUPLICATE_FACTS_IN_ANSWER_CONTEXT` | `NOT_CLOSED` | payloads: `0`; zero не доказан |
| `SOURCE_EVIDENCE` | `PRESERVED` | ArtifactStore/Resolver route сохранён |
| `LLM_DEDUPLICATION_GUESSWORK` | `NOT_CLOSED` | prevention contract отсутствует |

## Классификация дефекта

- Failed invariant: отсутствует explicit grouping и ровно одна interpretation-bearing representation на каждый semantic source scope.
- Owning component: answer-context assembly boundary после Gate 2.
- Blocker type: `MISSING_MAINTAINED_PRODUCT_BOUNDARY`.
- Причина не в VLM, OCR, crop extraction, Gate 1 или provider selection.

## Узкий corrective slice

Нужна одна factory-first граница, которая из существующих access-controlled ArtifactStore/ArtifactResolver records строит компактный answer context и отдельный safe selection receipt:

- переиспользует document/candidate/derivation identities;
- назначает стабильный evidence group;
- выбирает semantic table как единственную interpretation-bearing representation соответствующего visual-table scope;
- оставляет full-source/raw records только provenance/fallback refs, не копируя их значения в модельный контекст;
- отклоняет duplicate/missing selection fail-closed;
- не включает PDF bytes, crop bytes, provider output, RAG/vector data или sealed control vector;
- не меняет semantic JSON и Gemini prompt.

Этот corrective slice должен быть реализован в новой ветке и отдельном PR. В текущей audit-only ветке schema и runtime не менялись.

Private audit SHA-256: `6fbe5ec56cc8c5c9f46bbad23bca882ecd70736b3862f2cd57b116d94e492f04`.

Safe receipt SHA-256: `3e77a008b6a491e8650f7c377fcabaeb5bf4653515c747637f565d1c27303b64`.

Repository-safe evidence: [safe receipt](./BROKER_REPORTS_WORKFLOW_GOAL1_CONTEXT_SELECTION.receipt.safe.json).

## Проверки

- Read-only repository/live verifier: `passed`; Function bundles, prompts и valves совпадают.
- Semantic downstream/materialization, ArtifactStore/lifecycle и privacy regression: `34 passed`.
- `git diff --check`: `passed`.
- Private Goal 1 audit: ignored; private evidence в Git: `0`.

## Решение

`GOAL_1_CONTEXT_REPRESENTATION_SELECTION: NOT_CLOSED`
