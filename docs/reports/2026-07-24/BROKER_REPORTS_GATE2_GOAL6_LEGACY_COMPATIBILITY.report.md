# Broker Reports — Gate 2 Goal 6: legacy compatibility

Дата: 2026-07-24

Статус: `COMPLETED`

## Итог

Добавлен factory-managed compatibility policy:
`broker_reports_financial_evidence_compatibility_v1`.

Policy поддерживает pure dual-read трёх явно закреплённых schema families:

1. legacy `broker_reports_source_facts_v0`;
2. successor `broker_reports_financial_evidence_inputs_v1`;
3. specialized FNS `broker_reports_fns_2ndfl_source_facts_v1`.

Неизвестная schema version не угадывается и отклоняется.

## Pinned legacy replay

Legacy artifacts читаются только через:

- validator ID:
  `broker_reports_legacy_source_facts_validator_v1`;
- replay policy:
  `broker_reports_legacy_source_facts_replay_policy_v1`.

Pinned validator проверяет:

- exact legacy schema version;
- terminal `validator_status: passed`;
- run/case/package/document/validation identities;
- fact IDs, fact types, evidence refs и source location;
- complete coverage;
- exact partition selected refs между fact-covered и no-fact refs;
- отсутствие rejected/pending refs.

Reader вычисляет canonical artifact SHA-256 до чтения и повторно после чтения.
Любая mutation даёт `financial_evidence_compatibility_silent_rewrite`.
Replay повторяет тот же pinned read и требует exact schema, hash, validator,
read kind и classified records.

## Namespace classification

Legacy records остаются readable, но не становятся Registry aliases:

- broad IDs (`trade_operation`, `income`, `withholding_tax`,
  `fee_commission`, `cash_movement`, `currency_fx`,
  `position_snapshot`) → `legacy_financial_input`;
- `document_summary_evidence` → `evidence_kind`;
- `unknown_source_row` → `legacy_technical_disposition`.

Для всех legacy records:

- `mapping_status: unmapped`;
- `canonical_input_type_id: null`.

Initial Registry по-прежнему имеет `0` aliases. Ни один legacy broad ID не
совпадает с active Registry type ID.

## FNS specialized path

`broker_reports_fns_2ndfl_source_facts_v1` проходит собственный existing FNS
validator и читается как `fns_specialized`.

- fact namespace: `fns_specialized_fact_family`;
- mapping status: `separate`;
- canonical financial input type: отсутствует;
- migration через generic compatibility path запрещена с
  `financial_evidence_fns_mapping_not_adopted`.

FNS schema/facts не переписываются и не получают implicit Registry mapping.

## Single-write migration policy

Compatibility reader не выполняет migration автоматически и ничего не
persist-ит.

`prepare_migration_write` разрешает подготовить запись только если:

- source — успешно прочитанный legacy artifact;
- source payload всё ещё имеет exact recorded SHA-256;
- target — валидный `broker_reports_financial_evidence_inputs_v1`;
- каждый legacy record имеет ровно один explicit mapping;
- каждый mapping указывает на существующий target terminal ID;
- каждый mapping имеет bounded basis ref.

Migration receipt фиксирует:

- exact source ref/schema/hash/validator policy;
- `source_payload_rewritten: false`;
- `automatic_aliases_used: false`;
- полный explicit mapping и его SHA-256;
- exact target schema/artifact ID/hash;
- `write_contract: single_write_successor_only`.

Legacy write contract отклоняется всегда.

## Deterministic synthetic proof

- legacy artifact SHA-256:
  `bb7c5f892633be0ebe70f9e9d755ee4dba4bd41f99866a74ac582da61819bf04`;
- legacy records: `3`;
- legacy replay: `passed`;
- successor artifact SHA-256:
  `85d14fe8401d91b232ea13989e475f66ca8c4d33fefe39faa32ebb8eecaf1e6c`;
- explicit mappings SHA-256:
  `cda2787d730cb44d4a286868c5367e8c301e605587660a6b08cee21853bca398`;
- migration target SHA-256:
  `85d14fe8401d91b232ea13989e475f66ca8c4d33fefe39faa32ebb8eecaf1e6c`;
- FNS artifact SHA-256:
  `f24f2584ef00282a9100bd1eb0408b651d4461a6e69a2e15e17129330ef2ef10`;
- FNS records: `6`, all `separate`.

Proof использует только synthetic artifacts и не содержит customer values.

## Scope boundary

Compatibility layer не импортирует ArtifactStore/provider clients и не
записывает artifacts. Production runtime и stage не изменены. Full-scope
customer replay/qualification выполняется только в Goal 7 после merge этого
policy.

## Validation

- compatibility/replay tests: `16 passed`;
- compatibility + FNS + context/materialization/decision/Registry/catalog
  tests: `104 passed`;
- full Broker Reports suite: `1243 passed`, `20 skipped`;
- compatibility modules/tests ruff: `passed`;
- repository privacy guard: `3 passed`;
- private labels, values, filenames и provider output в Git: `ZERO`.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GATE2_GOAL6_LEGACY_COMPATIBILITY.receipt.safe.json).

## Acceptance

`LEGACY_ARTIFACTS: READABLE`

`SILENT_REWRITE: ZERO`

`AUTOMATIC_AMBIGUOUS_ALIASES: ZERO`

`FNS_PATH: UNCHANGED`

`REPLAY: PASSED`

`GOAL_6_LEGACY_COMPATIBILITY: COMPLETED`
