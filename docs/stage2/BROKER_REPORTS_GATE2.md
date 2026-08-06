# Broker Reports Gate 2

Status: `CURRENT_ENTRYPOINT`

Date: 2026-08-06

Это стартовая страница действующей реализации Broker Reports Gate 2. Для
понимания текущей системы не нужно последовательно читать DOC7-DOC33: эти
материалы являются историческим evidence, а не authority.

## Назначение

Broker Reports принимает сохранённый Gate 1 источник и строит одну
детерминированную, нефинансовую машинную проекцию документа:

```text
PDF | HTML | CSV | XLSX
        -> format-specific extraction (private Full Evidence)
        -> CanonicalNormalizerFactory.create
        -> validated CanonicalArtifactV1
        -> immutable publication and atomic activation
        -> CanonicalReaderFactory.create
        -> format-agnostic consumer
```

Gate 1 владеет authenticated intake, оригинальными байтами и выбором маршрута.
Gate 2 извлекает структуру, нормализует её, проверяет completeness, публикует
неизменяемую версию и читает её через один reader. Gate 3 ещё не реализован; он
будет владеть task-specific LLM projection и финансовой семантикой.

## Четыре разные границы

```text
Full Evidence
!= CanonicalArtifactV1
!= neutral diagnostic projection
!= future Gate 3 financial result
```

- Full Evidence содержит оригинал, parser units, координаты, crops и provider
  proposals. Оно приватно и не является публичной машинной моделью.
- `CanonicalArtifactV1` содержит упорядоченные containers, nodes, tables,
  issues и компактный provenance. Это единственный публичный Gate 2 schema.
- `render_neutral_canonical_projection` — reader-only diagnostic, а не
  продуктовый LLM prompt или отдельный output contract.
- Финансовые facts, roles, ontology и reconciliation принадлежат будущему Gate
  3 и запрещены в `CanonicalArtifactV1`.

## Текущие authority

| Authority | Нормативная точка |
| --- | --- |
| gate numbering and boundaries | [Pipeline Gates v1](contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md) |
| public logical schema | [Canonical Artifact v1](contracts/BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md) и [JSON Schema](contracts/BROKER_REPORTS_CANONICAL_ARTIFACT.v1.schema.json) |
| normalization | `CanonicalNormalizerFactory.create` |
| storage lifecycle | [Canonical Storage and Lifecycle v1](contracts/BROKER_REPORTS_CANONICAL_STORAGE_LIFECYCLE.v1.md) и `CanonicalArtifactStoreFactory.create` |
| public read | [Canonical Reader v1](contracts/BROKER_REPORTS_CANONICAL_READER.v1.md) и `CanonicalReaderFactory.create` |
| Gate 2 exit | [Gate 2 Exit Contract v1](contracts/BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) |
| implementation locations | [Gate 2 implementation map](architecture/BROKER_REPORTS_GATE2_IMPLEMENTATION_MAP.v1.md) |
| safe modification | [Gate 2 safe-change guide](operations/BROKER_REPORTS_GATE2_SAFE_CHANGE_GUIDE.v1.md) |
| Gate 3 boundary | [Gate 3 handoff v1](contracts/BROKER_REPORTS_GATE3_HANDOFF.v1.md) |
| branch lifecycle | [Broker Reports branch lifecycle](operations/BROKER_REPORTS_BRANCH_LIFECYCLE.v1.md) |

## Current product boundary

Canonical storage, reader and compatibility shadows are implemented and
tested. `CANONICAL_GATE2_READ_ENABLED=false` remains the global product
default, `gate2_handoff_v0` remains the legacy product compatibility authority,
and neither Wave 2 nor primary cutover was performed. Diagnostic code may read
canonical versions only through `CanonicalReaderFactory`; it cannot silently
fall back, call providers or write product state.

## Historical material

`BROKER_REPORTS_CURRENT_STATE.v1.*`, numbered DOC reports/receipts, closed PRs
and the pre-DOC34 checkpoint are historical snapshots. They may explain how a
decision was reached but cannot override the CURRENT contracts above. A
conflict is resolved in this order: versioned contract, maintained factory,
compatibility delegate, then historical evidence.
