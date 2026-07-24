# Broker Reports — Gate 2 Goal 4: deterministic materialization

Дата: 2026-07-24

Статус: `COMPLETED`

## Итог

Добавлен явно версионированный successor contract:
`broker_reports_financial_evidence_inputs_v1`.

Смысл legacy `broker_reports_source_facts_v0` не изменён.

Validated model decision преобразуется в terminal financial evidence artifact
только детерминированным кодом. Модель не создаёт system metadata.

## Authority boundaries

Materialization разделена на четыре ограниченных authority:

1. contracts и общие deterministic primitives;
2. integrity-sealed authoritative source package;
3. materializer;
4. independent artifact validator.

Production path:

- decision сначала валидируется canonical Goal 3 contract;
- Registry version/hash должны точно совпадать;
- source scope/family и полный candidate set должны совпадать;
- candidate `source_ref` и `value_type` защищены authority hash;
- source package должен пройти собственную integrity verification;
- materializer создаёт artifact;
- independent validator повторно проверяет shape, identities, projections,
  terminal state и integrity.

ArtifactStore, provider clients, customer state и Gate 3 не входят в этот
boundary.

## Code-owned materialization

Код создаёт:

- stable `input_id`, `unclassified_input_id`, `coverage_id` и `artifact_id`;
- Registry ID, version и hash;
- literal source values без перезаписи;
- deterministic normalized comparison values;
- date/period и currency/unit projections;
- source sign по каждому numeric source value;
- source evidence refs;
- document/page/table/row/cell lineage;
- normalization/document/package/scope ownership;
- completeness, restriction codes и issue refs;
- terminal и artifact integrity SHA-256.

Stable input identity использует Registry identity policy, source scope,
identity-role source refs/comparison values и source evidence refs. Execution
metadata не меняет input identity.

Нормализация консервативна:

- decimal — finite `Decimal`;
- integer — strict integer;
- date — ISO date;
- currency — normalized uppercase;
- text/reference/period/unit — Unicode NFKC, whitespace collapse и casefold
  только для comparison value.

Literal value всегда сохраняется отдельно.

## Terminal dispositions

`typed_input`:

- публикует ровно один Registry-bound typed input;
- повторно проверяет required roles;
- сохраняет literal values и полную source provenance.

`unclassified_financial_input`:

- не публикует typed input;
- создаёт отдельный terminal artifact с `registry_gap: true`;
- materialization fail-closed, если decision не связал каждый candidate ref;
- все literal values, normalized comparisons, source refs и lineage
  сохраняются.

`no_financial_input` и `unsupported`:

- не создают фиктивный financial object;
- закрывают source scope отдельным terminal coverage record.

## Stable synthetic proof

Для полностью синтетического fixture:

- Registry SHA-256:
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`;
- source package SHA-256:
  `17ccc7187647d44730998319975d90d15d80606313503499fdc4c3ff6b6414ba`;
- typed input ID:
  `finin_706b576cdcae04542f72cfb64adc9214`;
- typed artifact ID:
  `finset_989fa14d437e9e1a43d85c5e1fa4aff0`;
- typed artifact integrity:
  `9400c63f58cc4dd08838200417fb4f10d3a79a47276772d9408edbcbb5cef094`;
- unclassified input ID:
  `finun_ff0571b5c429bfcd713f052885992ea0`;
- unclassified artifact ID:
  `finset_d4c931ce149a9866401c10c7ecb98c7f`;
- unclassified artifact integrity:
  `24817aa2db9ae4bca5b1c267e9396909979d084d2ad3db9e019e7b3fdf88a9e1`;
- no-financial coverage ID:
  `finclose_a533238197915908119c98074f9d8723`.

Эти IDs/hashes доказывают deterministic fixture behavior и не содержат
customer values.

## Scope boundary

Goal 4 не создаёт model-facing context projection — это отдельный Goal 5.
Production runtime не переключён, stage не изменён, Gate 3 fields запрещены
exact-shape validator и recursive forbidden-field check.

## Validation

- materialization tests: `20 passed`;
- materialization + decision + Registry + catalog tests: `64 passed`;
- full Broker Reports suite: `1211 passed`, `20 skipped`;
- four new/refactored modules and tests ruff: `passed`;
- repository privacy guard: `3 passed`;
- private labels, values, filenames и provider output в Git: `ZERO`.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GATE2_GOAL4_DETERMINISTIC_MATERIALIZATION.receipt.safe.json).

## Acceptance

`MODEL_SYSTEM_METADATA: ZERO`

`TYPED_INPUT_MATERIALIZATION: DETERMINISTIC`

`UNCLASSIFIED_VALUE_LOSS: ZERO`

`SOURCE_PROVENANCE: COMPLETE`

`STABLE_IDENTITY: PASSED`

`GATE3_FIELDS: FORBIDDEN`

`GOAL_4_DETERMINISTIC_MATERIALIZATION: COMPLETED`
