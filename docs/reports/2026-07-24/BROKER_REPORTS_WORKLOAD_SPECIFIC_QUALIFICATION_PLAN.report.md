# Broker Reports — Workload-specific qualification plan

Дата: 2026-07-24.

Статус плана: `COMPLETED`.

## Qualification identity

Единица статуса:

`exact model ID × provider profile/route × workload × contract version`.

Минимальный receipt key:

```text
model_id
provider_profile
provider_route_revision
workload
input_contract_version
output_contract_version
prompt_contract_version
adapter_projection_revision
canonical_validator_revision
pricing_snapshot_date
```

Alias, family status и общий `qualified_models_total` не являются admission
authority. Один exact model может быть qualified для source и not qualified
для financial evidence.

## Gate sequence

| Gate | Действие | Pass condition | Calls/data |
| ---: | --- | --- | --- |
| 0 | exact identity/publication preflight | exact stable ID виден через maintained connection; no alias drift | 0 |
| 1 | schema-only dry build | provider projection deterministic; size/keywords recorded; canonical schema unchanged | 0 |
| 2 | provider capability probe | provider accepts exact schema/mode; usage identity available | one minimal synthetic call |
| 3 | frozen synthetic secretary benchmark | все terminal thresholds 100%, inventions/duplicates/truncations 0 | bounded non-customer |
| 4 | workload-specific non-customer live fixture | parseable strict result; one call; no repair/fallback | bounded non-customer |
| 5 | production canonical validator | passed unchanged validator/materializer | same result |
| 6 | bounded actual-corpus shadow | safe aggregate receipt, no raw output in Git | separately authorized private corpus |
| 7 | full-scope | all prior exact-key gates passed; cost preflight; no customer run in this research slice | separate program |

Failure at любой ступени прекращает продвижение exact subject. Нельзя
перепрыгнуть к full-scope на основании model card или source success.

## Failure classes

| Class | Определение | Разрешённое следующее действие |
| --- | --- | --- |
| `MODEL_QUALITY_FAILURE` | schema accepted и route executed, но repeated canonical clerical errors | prompt diagnosis once; then reject exact workload |
| `PROVIDER_SCHEMA_LIMITATION` | official/native API rejects required supported shape | tool-schema alternative only if equally strict; otherwise reject |
| `OPENWEBUI_ADAPTER_LIMITATION` | native API can express contract, maintained adapter/projection cannot | narrow adapter fix + new revision/qualification |
| `HARNESS_ROUTE_MISSING` | qualification runner never invokes required workload | add bounded route; no model judgement |
| `MODEL_NOT_PUBLISHED` | exact stable ID absent from maintained aggregate inventory | publish through existing connection; do not activate |
| `QUOTA_OR_RATE_LIMIT` | 429/quota prevents terminal test | record terminal; retry only in new authorized attempt |
| `OUTPUT_TRUNCATION` | provider stop/max token before complete object | adjust bounded cap within budget or reject |
| `UNKNOWN` | evidence cannot separate layers | remain not qualified; collect narrower evidence |

Free JSON fallback, malformed-output repair, hidden retry and weakening of
canonical validator запрещены.

## Current evidence reclassification

| Subject | Previous observation | Correct class/status |
| --- | --- | --- |
| GPT-5 Nano × any workload | 0 calls, absent `/api/models` | `MODEL_NOT_PUBLISHED`; not quality failure |
| Gemini 3.1 FL × source v3 | live passed | retain workload evidence; formal receipt/version binding still required |
| Gemini 3.1 FL × financial v1 | provider returned; canonical unclassified shape invalid | `UNKNOWN` between projection/prompt/model; minimal branch fixture next |
| Gemini 3.5 FL × source v3 | live passed | retain workload evidence |
| Gemini 3.5 FL × financial v1 | 0 calls | `HARNESS_ROUTE_MISSING` |
| Haiku 4.5 × source v3 | live passed | retain workload evidence |
| Haiku 4.5 × financial v1 | schema response format rejected | `PROVIDER_SCHEMA_LIMITATION` or `OPENWEBUI_ADAPTER_LIMITATION`; not model failure |
| DeepSeek v4 × strict workloads | official JSON-only route | `PROVIDER_SCHEMA_LIMITATION` for current contract |

## Workload-specific batches

### Batch A — already published Gemini

1. Gemini 3.1 source formal replay, then domain.
2. Gemini 3.5 source formal replay, then domain.
3. Add financial harness route for 3.5.
4. Run minimal single-branch financial fixtures for 3.1/3.5.
5. Check checksum only after schema/canonical gates.

Это не требует architecture change; только qualification harness and
receipt discipline.

### Batch B — publish cheapest candidates

1. Publish GPT-5 Nano exact snapshot.
2. Publish Gemini 2.5 Flash-Lite stable ID.
3. Publish GPT-4.1 Nano exact snapshot.
4. Dry-build all four workload schemas before any provider call.
5. Execute each subject independently in ascending expected cost.

Publication/config change не является production release.

### Batch C — diagnostic reserves

- GPT-5.4 Nano and GPT-4o Mini only after cheaper strict candidates fail;
- Haiku only to isolate adapter/native schema boundary;
- DeepSeek only after official strict tool-schema evidence, not by prompt
  JSON convention.

## Synthetic benchmark execution

For each exact subject:

1. load frozen `gate2_secretary_v1`;
2. record provider schema acceptance separately;
3. pass provider output directly to canonical workload validator;
4. feed safe observations into deterministic comparator;
5. record latency/usage/cost;
6. emit safe report without raw output/expected values;
7. require all 12 common cases plus workload-specific fixtures.

Comparator report alone cannot mark production qualified. Actual canonical
validator result is authoritative.

## Qualification receipt states

Allowed terminal states:

- `QUALIFIED_FOR_EXACT_WORKLOAD`;
- `NOT_QUALIFIED_MODEL_QUALITY`;
- `NOT_QUALIFIED_PROVIDER_SCHEMA`;
- `BLOCKED_ADAPTER`;
- `BLOCKED_HARNESS`;
- `BLOCKED_NOT_PUBLISHED`;
- `BLOCKED_QUOTA`;
- `BLOCKED_TRUNCATION`;
- `UNKNOWN_NOT_QUALIFIED`.

No general model-wide downgrade may erase a passed subject receipt.
Lifecycle/prompt/adapter/contract revision changes invalidate only receipts
whose exact key changed.

## Release boundary

После qualification:

- selector chooses `CHEAPEST QUALIFIED FOR THIS EXACT WORKLOAD`;
- fallback also должен иметь exact workload receipt;
- selection snapshot records prices and contract revisions;
- full-scope and checksum are separate gates;
- production migration is a separate implementation/qualification program.

В этом research slice provider calls, stage mutations, actual-corpus calls и
production release: `ZERO`.
