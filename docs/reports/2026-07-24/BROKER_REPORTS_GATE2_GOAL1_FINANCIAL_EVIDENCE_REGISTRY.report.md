# Broker Reports — Gate 2 Goal 1: Financial Evidence Registry authority

Дата: 2026-07-24

Статус: `COMPLETED`

## Итог

Создан code-owned `Gate2FinancialEvidenceRegistryFactory` с immutable,
versioned и deterministic snapshot:

- registry ID:
  `broker_reports_gate2_financial_evidence_registry`;
- registry version:
  `broker_reports_gate2_financial_evidence_registry_v1`;
- canonical empty authority snapshot SHA-256:
  `7da34f4887c8e3b4f90b917a32b35d544c6924daaf1ebc690f6d1661a354971f`.

Goal 1 намеренно не активирует типы. Initial bounded catalog является
отдельным Goal 2 route. Это не позволяет смешать authority contract с
решением о корпусно доказанных типах.

## Boundary

Registry declaration владеет:

- immutable `input_type_id` и registry version;
- source-oriented definition и semantic class;
- lifecycle;
- compatible source families;
- required, optional и forbidden roles;
- role value type, cardinality и source-ref policy;
- date/period и currency/unit requirements;
- source-sign policy;
- source-level identity/deduplication material;
- provider description;
- materialization, validation и context projection profile IDs;
- safe examples/counterexamples;
- evidence/test refs;
- version-scoped compatibility metadata.

Registry не импортирует provider clients, ArtifactStore, runtime, filesystem,
network или customer data. Runtime integration и provider schemas не входят в
этот PR.

## Factory guarantees

Factory:

- сортирует declarations и aliases перед snapshot hashing;
- возвращает только frozen dataclasses и tuples;
- создаёт одинаковый hash независимо от input order;
- строит provider type enum и profile lookups из одного snapshot;
- исключает retired/deprecated types из model-facing enum;
- не принимает свободный type ID;
- сохраняет alias как version-scoped compatibility identity, а не canonical
  type.

Обязательные anti-drift anchors:

- `FACTORY_REQUIRED`;
- `FORBIDDEN`.

## Fail-closed consistency

Build отклоняется при:

- duplicate type IDs;
- duplicate/colliding aliases;
- conflicting role sets;
- missing/duplicate role specs;
- invalid lifecycle, semantic class или policy namespace;
- state/event date-policy contradiction;
- amount при forbidden currency/unit policy;
- incomplete source identity;
- missing examples/counterexamples;
- active type without evidence or tests;
- semantic fingerprint change под pinned ID;
- alias cycle или unknown target;
- compatibility target outside snapshot;
- legacy mapping without artifact-version scope.

## Non-goals

Не реализованы:

- initial input type catalog;
- provider decision schema;
- materialization;
- context projection;
- legacy artifact adapter;
- Gate 3, tax/declaration semantics или accounting ledger.

## Validation

- registry tests: `13 passed`;
- registry + closed-world bundle tests: `21 passed`;
- full Broker Reports suite: `1160 passed`, `20 skipped`;
- new module/test ruff: `passed`;
- compileall: `passed`;
- repository privacy guard: `passed`.

Полный `ruff` для legacy `broker_reports_gate1/__init__.py` сохраняет 64
существовавших F401, не связанных с этим route. Они не изменялись и не
скрывались исправлением Goal 1.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GATE2_GOAL1_FINANCIAL_EVIDENCE_REGISTRY.receipt.safe.json).

## Acceptance

`REGISTRY_FACTORY: PURE_AND_DETERMINISTIC`

`REGISTRY_SOURCE_OF_TRUTH: ONE`

`FREE_FORM_TYPE_IDS: ZERO`

`CUSTOMER_DATA_IN_REGISTRY: ZERO`

`TAX_OR_DECLARATION_SEMANTICS: ZERO`

`CONSISTENCY_VALIDATION: FAIL_CLOSED`

`GOAL_1_REGISTRY_AUTHORITY: COMPLETED`
