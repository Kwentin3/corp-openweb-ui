# Broker Reports GOAL G3.1 — Minimal Gate 3 Contract

Status: `COMPLETED`

Date: 2026-08-06

Repository baseline: `main == origin/main == 288f7a8439baba558ebe2d70e1fb0699f8f163b7`

Scope: contract-only Gate 3 boundary. No Gate 2 runtime, provider route,
ArtifactStore registration, OpenWebUI workflow, product flag or stage state was
changed. G3.2 was not started.

## GOAL_STATUS

```text
GOAL_STATUS = COMPLETED
NEXT_ALLOWED_GOAL = G3.2 — LLM-friendly projection
```

## WHAT_WAS_ACHIEVED

Gate 3 now has one readable, inactive normative boundary:

```text
active validated CanonicalArtifactV1 via CanonicalReaderFactory.create
-> Gate3ProjectionV1
-> Gate3LabelingResponseV1 proposal
-> code validation and alias restoration
-> validated FinancialAnnotationsV1
```

The only logical input is the exact active canonical version. The only
authoritative Gate 3 output is a validated `FinancialAnnotationsV1` sidecar.
Projection and provider response are intermediate contracts, not new document
or financial authorities.

Sparse positive-only semantics are explicit: the model may return only
supported alias/label pairs; uncertainty or non-match is omission. Empty
annotations are valid and omission makes no negative or completeness claim.
The model cannot provide canonical refs or define a new label.

## WHAT_WAS_REUSED

- the public `CanonicalReaderFactory.create` Gate 2 read boundary;
- existing `CanonicalArtifactV1` node IDs, list positions and table row/cell
  coordinates;
- the current Pipeline Gates, Gate 3 handoff and architecture authority map;
- the real `CanonicalNormalizerFactory` and canonical validator in executable
  compatibility tests;
- the repository's Draft 2020-12 JSON Schema validation stack.

## WHAT_WAS_ADDED

- [Minimal Labeling v1](../../stage2/contracts/BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md),
  the inactive human-readable normative contract;
- closed schemas for
  [Gate3ProjectionV1](../../stage2/contracts/BROKER_REPORTS_GATE3_PROJECTION.v1.schema.json),
  [Gate3LabelingResponseV1](../../stage2/contracts/BROKER_REPORTS_GATE3_LABELING_RESPONSE.v1.schema.json)
  and
  [FinancialAnnotationsV1](../../stage2/contracts/BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v1.schema.json);
- one shared
  [Gate3CanonicalTargetV1](../../stage2/contracts/BROKER_REPORTS_GATE3_TARGET.v1.schema.json)
  locator grammar, so projection and sidecar do not duplicate canonical-target
  meaning;
- positive, negative, empty-result, closed-schema, canonical-coordinate and
  architecture-boundary tests;
- current-contract references in Pipeline Gates, Gate 3 handoff and the
  architecture authority map.

The existing historical Gate 2 audit pin was updated only with the exact LF
SHA-256 of the revised authority map; its original evidence pins remain
unchanged.

## WHAT_WAS_NOT_NEEDED

- changes to `CanonicalArtifactV1` or any Gate 2 implementation;
- a renderer, provider call, retry, repair or fallback;
- a financial dictionary or independent Prompt/Skill/Tool meaning source;
- exhaustive `unclassified`, `unsupported` or `no_financial_input` outcomes;
- Financial Domain, relations, graph, calculations or tax methodology;
- an ArtifactStore type, database, persistence adapter or product route;
- OpenWebUI integration, Gate 4, activation or legacy deletion.

## ACCEPTANCE_EVIDENCE

Focused contract and architecture verification:

```text
57 passed, 1 skipped in 27.03s
```

This included the new G3.1 schema/canonical tests, Pipeline Gates boundary
tests, architecture tests and the historical authority-audit replay.

Full offline service verification, excluding live/provider tests and one
Windows line-ending-only test:

```text
2685 passed, 5 skipped, 1 deselected in 825.97s
```

The deselected test compares generated bundle working-tree bytes directly.
All three checked-in bundles use CRLF in this Windows checkout while the
builder emits LF. After CRLF-to-LF normalization, every rebuilt bundle is
exactly equal to its checked-in counterpart. No bundle or runtime file was
changed.

Additional checks:

```text
all four new JSON documents parsed successfully
Draft202012Validator.check_schema passed for all four schemas
git diff --check = clean
provider calls = 0
stage mutations = 0
```

## KNOWN_LIMITATIONS

- G3.1 defines DTO meaning only; `Gate3ProjectionV1` has no renderer yet.
- The financial dictionary and its exact label set do not exist yet.
- JSON Schema closes response syntax, but alias existence, known-label
  membership, canonical target resolution and duplicate restored pairs require
  the later G3.4 code validator.
- `FinancialAnnotationsV1` is not registered or persisted; that belongs to
  G3.5.
- No quality, coverage, provider or product-read claim is made.
- The direct bundle byte-equality test remains checkout-line-ending-sensitive
  on Windows; its normalized content invariant is green.

## KISS_CHECK

1. **Можно ли было решить задачу проще?** Нет. Три требуемых DTO и один общий
   locator schema — минимальная форма без дублирования target grammar.
2. **Создан ли новый слой, без которого можно обойтись?** Нет. Добавлена только
   неактивная контрактная граница; runtime-слой отсутствует.
3. **Появился ли второй источник истины?** Нет. Canonical meaning остаётся у
   Gate 2, будущий словарь остаётся единственным владельцем label meaning.
4. **Добавлено ли что-то только ради будущего использования?** Нет. Каждое поле
   прямо требуется G3.1 для canonical binding, версий словаря/инструкции,
   модели, аннотаций и validated status.
5. **Можно ли простыми словами объяснить результат GOAL?** Да: Gate 3 получает
   один нормализованный документ и отдельно сохраняет только проверенные
   ссылки на его элементы с известными финансовыми бирками.

## NEXT_ALLOWED_GOAL

```text
G3.2 — LLM-friendly projection
```

Работы G3.2 не начинались.
