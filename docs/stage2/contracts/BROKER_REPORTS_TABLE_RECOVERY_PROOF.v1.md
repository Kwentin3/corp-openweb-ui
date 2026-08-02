# Broker Reports Table Recovery Proof v1

Статус контракта: active for inactive DOC5 proof receipts only.
JSON Schema: `BROKER_REPORTS_TABLE_RECOVERY_PROOF.v1.schema.json`.

## Назначение

Контракт фиксирует `PASSED` или честный `BLOCKED` для frozen PDF corpus. Он не является product runtime contract и не изменяет Managed Document v1.

## Инварианты `PASSED`

Для `PASSED` все nullable proof counters обязаны быть integers, а также:

- 22 отказа классифицированы, unclassified равен нулю;
- все critical tables имеют validated grid;
- baseline regressions равны нулю;
- rows/cells совпадают с независимым PDF gold;
- unresolved, multiple-owner, duplicate, invented, dropped и critical mismatch counters равны нулю;
- PDF-vs-View parity равна `PASSED`;
- DOC1, product route, provider и live state не изменены;
- generated bundle diff, new skips, test failures и errors равны нулю.

## Инварианты `BLOCKED`

Для `BLOCKED` receipt обязан содержать:

- `last_proven_stage`;
- `affected_tables`;
- `first_failure_point`;
- `available_geometry`;
- `missing_evidence`;
- `why_logical_grid_cannot_be_proven`;
- `minimal_required_contract_change`;
- `next_operator_action`.

Неизмеренные counters остаются `null`, а не подменяются нулём. `pdf_vs_view_table_semantic_parity` должна быть `BLOCKED` или `FAILED`.

## Privacy и integrity

Receipt содержит только safe IDs, агрегаты, commit identities и terminal statuses. Source bytes, values, private paths, prompts и provider payloads запрещены.

`integrity_sha256` равен SHA-256 canonical JSON после удаления самого поля; canonical JSON использует UTF-8, sorted keys и separators `(',', ':')`.
