# Broker Reports — Gate 2 ambiguity discipline, Goal 2

Дата: 2026-07-25

Статус: `SEMANTIC_CONTEXT_SUFFICIENCY: GAP_IDENTIFIED`

## Результат

Текущий successor model input сохраняет literal values, value types,
package-bound refs и allowed roles, но недостаточен для безопасного различения
semantic hypotheses.

Проблема не в отсутствии самих literals. Проблема в потере bounded structural
associations между ними.

## Где теряется контекст

Gate 1 package уже содержит:

- `model_source_projection` с rows/cells;
- per-cell `header_label`;
- `normalized_header_descriptors`;
- row kind/role;
- source-value index с row/cell association;
- section/text descriptors, когда они существуют.

Canonical compact-context helper уже умеет строить bounded row/header
projection (`gate2_llm_context.py:303–346`).

Но deterministic Financial scope:

- извлекает literals из `model_source_projection`;
- сохраняет lineage;
- назначает allowed roles только по regex/value type;
- не переносит visible header/row association в successor model input.

`_infer_type` (`gate2_deterministic_financial_scopes.py:943`) различает только
date, decimal, currency и generic text. Header semantics на role admission не
влияет.

`Gate2FinancialEvidenceSuccessorRunner.model_input`
(`gate2_financial_evidence_successor.py:304`) затем создаёт плоские:

- `eligible_types`;
- `source_values`.

Row/column/section composition отсутствует.

## Context-field assessment

| Field | Exists in Gate 1 | Current model input | Needed | Decision |
|---|---:|---:|---:|---|
| Literal source label | Yes | Yes, as flat value | Yes | Preserve and associate |
| Row heading/role | Yes for table sources | No | Yes | Add bounded source context |
| Section heading/role | Sometimes | No | Useful | Add only when authoritative |
| Neighbouring header | Sometimes | No | Bounded only | Include only authorized in-scope header; never neighbour rows |
| Table column meaning | Yes | No | Yes | Add visible per-value label |
| Bounded descriptive text | Yes for text segments | Literal only | Yes | Preserve scoped segment association |
| Source family | Yes | No | Not needed by model for two cases | Keep code-only |
| Document section role | Sometimes | No | Useful discriminator | Include bounded source-owned role |
| Printed-total/detail indicator | Sometimes as row role/header | No | Yes when authoritative | Preserve; do not invent |
| Ambiguity evidence | Derivable by code | No | Yes for admission | Keep code-owned; remove unsafe typed branch |

## Per-case effect

### Multiple hypotheses

Missing association is causally material:

- two labels and two amounts became one flat candidate list;
- no authoritative pair/group relationship reached the model;
- both Registry types remained shape-compatible.

Bounded row/value context would make the competing hypotheses explicit, but
context alone не является достаточной safety boundary. Code уже может доказать
structural ambiguity (multiple competing role candidates without unique
association) и должен не генерировать typed branch.

### Explicit unclassified

Literal disconfirming label уже был передан. Поэтому дополнительный text сам по
себе не исправляет safety:

- модель смогла оставить optional `source_label=null`;
- typed cash branch оставался schema-valid.

Здесь context sufficient для semantic rejection, но typed admission не требует
использовать semantic evidence.

## Target bounded context

Рекомендуется successor model-input version с package-owned groups:

- `source_group` без document/path/provenance IDs;
- bounded `row_role` / `section_role`, только если authoritative;
- values nested in their source group;
- каждый value сохраняет существующий `source_value_ref`;
- `visible_label`/column meaning рядом с value;
- optional bounded visible section/header text;
- no neighbour values outside deterministic scope.

Не передавать:

- provenance/candidate/relation graph;
- internal paths;
- document/system IDs;
- ownership/completeness/audit;
- expected disposition;
- deterministic admission decision as a textual hint.

Typed admission state должен применяться кодом к package-specific schema, а не
возвращаться модели как совет.

## Ownership

- Gate 1 owns neutral visible structure and literals.
- Deterministic scope factory owns bounded selection/grouping.
- Typed-admission policy owns whether typed type is structurally available.
- Model owns semantic choice only among admitted branches.
- Canonical validator rechecks admission identity and exact refs.

## Acceptance

- `SEMANTIC_CONTEXT_SUFFICIENCY: GAP_IDENTIFIED`
- `MISSING_USEFUL_CONTEXT: EXPLICIT`
- `SYSTEM_METADATA_REINTRODUCTION: ZERO`

No production/runtime code changed. Provider/customer calls: 0.
Следующий шаг: Goal 3 deterministic eligibility audit.
