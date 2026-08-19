# Broker Reports — Provider Failure, Fact-Set Mismatch and Inventory G5.84

Дата: `2026-08-17`
Статус: `PARTIAL — PROVIDER_RETRY_POLICY_BOUNDARY_REACHED`
Ветка: `feature/gate5-tax-period-category-aggregation`

## Итог

Три класса больше не смешиваются:

- chunk `24` — операционный HTTP `502` / non-JSON provider failure до
  появления semantic role response;
- chunk `106` — существующий semantic response с exact duplicate alias
  `f005`;
- рост Gate 4 `391 → 1783` — полностью объяснён version-bound заменой
  Canonical/Gate 3 inventory и восстановленными atomic facts.

По provider branch сработал предусмотренный strategic stop: текущие Gate 3
authority и factories требуют один вызов и прямо запрещают retry. Общего
bounded operational retry contract нет. Magic count не добавлен, ordinary
replay не выполнялся.

```text
PROVIDER_FAILURE_SEMANTICS_PROVEN
TRANSPORT_FAILURE_SEPARATED_FROM_SEMANTIC_REJECTION
PROVIDER_RETRY_POLICY_BOUNDARY_REACHED

GATE3_FACT_SET_MISMATCH_SOURCE_QUALIFIED
FACT_SET_MISMATCH_MINIMAL_UNSAFE_UNIT_PROVEN

CURRENT_FACT_INVENTORY_ACCOUNTED
UNEXPLAINED_FACT_DELTA_ZERO
INVENTED_FACTS_ZERO
INVENTED_RELATIONS_ZERO
```

Не заявляются:

```text
BOUNDED_OPERATIONAL_RETRY_CONTRACT_PROVEN
READY_TO_RESUME_DOWNSTREAM_E2E_AFTER_REPLAY
READY_TO_ENTER_GATE5_FROM_NEW_ORDINARY_ARTIFACT
```

## A. Provider failure semantics

Exact incident chunk `24`:

| Поле | Результат |
| --- | --- |
| pass 1 | `32` validated fact identities |
| failed phase | `role_labeling` |
| HTTP | `502` |
| provider payload | `non_json_provider_response` |
| usable semantic response | `0` |
| mapped code | `gate2_model_provider_unavailable` |
| calls / retries | `1 / 0` |

Фактический owner chain:

```text
Gate3RoleLabelingFactory.create_from_chunk
→ shared Gate2StructuredModelClientFactory client seam
→ provider adapter / OpenWebUI completion boundary, exactly once
→ provider_error_code: 500/502/503/504 → gate2_model_provider_unavailable
→ Gate3ChunkBatchLabelingFactory: provider_failed at role_labeling
```

Префикс `gate2_` здесь — legacy family name общего structured model client,
а не доказательство, что отказ произошёл в Gate 2 semantics. Batch корректно
сохранил phase=`role_labeling` и не создал synthetic roles из pass 1.

В repository contracts найдено не разрешение на operational retry, а обратная
граница: Role Labeling и Chunk Batch запрещают retry/repair/fallback, adapters
экспонируют one-shot `invoke_native_once` / `_invoke_completion_once`, а
execution metadata фиксирует `retry_calls=0`. Qualification-only transport
contracts с явно заданным `retry=0` не являются production policy для Gate 3.

Поэтому G5.84 не вводит cross-provider retry framework. Будущий отдельный
contract может разрешить bounded operational повтор только когда первого
semantic result не существовало, и только с тем же source context, model,
instruction, Role Pack и response contract. Полученный, но отвергнутый
validator-ом semantic response повторять нельзя.

## B. Exact `fact_set_mismatch`

Pass 1 chunk `106` содержит aliases `f001…f026`. Pass 2 вернул `27` entries и
`26` unique aliases:

| Класс | Exact result |
| --- | ---: |
| missing aliases | `0` |
| unknown/extra aliases | `0` |
| changed aliases | `0` |
| duplicate aliases | `f005 × 2` |
| extra occurrences | `1` |
| deduplicated sequence equals pass 1 | `true` |
| reorder-only | `false` |

Один `f005` имел неверный label, второй — ожидаемый `DIVIDEND_INCOME`; оба
несли четыре role bindings. Выбирать второй ответ было бы repair/best-of.
Minimal unsafe unit — exact pass-1 fact `f005`, не chunk и не соседние `25`
facts.

Узкий fix использует только существующие G5.83 outcomes:

1. unique returned alias-set обязан точно равняться полному pass-1 set;
2. все occurrences известного duplicated alias отбрасываются целиком;
3. pass-1 identity сохраняется, все четыре allowed roles становятся
   explicit `missing`;
4. остальные facts восстанавливаются только по exact unique alias и в pass-1
   order;
5. missing/unknown/unequal alias-set по-прежнему отклоняет весь proposal.

Similarity, value, array-position или соседство не используются. Schema,
merge protocol и generic partial-response framework не добавлены.

Exact stored-output replay chunk `106` без provider вызова:

| Metric | Result |
| --- | ---: |
| chunks validated | `1/1` |
| annotations retained | `26` |
| role-complete | `25` |
| role-incomplete | `1` |
| rejected roles | `4` |
| provider calls | `0` |

Полный frozen replay прежних `140` chunks также остался exact-valid:
`140/140`, `1489` facts текущего документа, `33` прежних role rejections,
Gate 4 `1783`, provider calls `0`.

## C. Deterministic fact inventory accounting

Accounting выполнен через текущие public Gate 3 persistence, Canonical reader
и Gate 4 runtime factories на изолированных stores. Direct SQL и просмотр
`1783` facts глазами не использовались.

### Delta `391 → 1783`

| Причина | Facts |
| --- | ---: |
| G5.76 case baseline | `391` |
| old non-atomic pseudo-facts, исключённые текущим admission | `-58` |
| old-version atomic node assertions, отсутствующие в replacement pass 1 | `-10` |
| новые atomic facts из 135 ранее contract-valid chunks | `+1287` |
| facts пяти ранее целиком подавленных chunks | `+173` |
| **current case** | **`1783`** |
| **unexplained delta** | **`0`** |

Три неизменившихся документа дают exact-hash-equal `294` facts. Старый large
document имел `39` atomic facts; `29` exact required-role source assertion
signatures воспроизведены. Оставшиеся `10` были version-bound `node` facts и
не присутствуют в replacement pass-1 inventory: `8 SECURITY_PURCHASE`,
`1 SECURITY_DISPOSAL`, `1 COMMISSION_TOTAL` на exact pages
`3, 8×2, 11, 12, 13, 14, 15, 17, 60`. Это явный отрицательный sparse result,
а не скрытое сохранение старой sidecar или reconciliation.

Current document `1489`:

| Разрез | Counts |
| --- | --- |
| target kind | `table_cell=903`, `table_row=584`, `node=2` |
| atomicity | `structural=1487`, `unique_literal_anchor=2` |
| type | `TAX_WITHHELD=746`, `DIVIDEND_INCOME=539`, `SECURITY_PURCHASE=77`, `SECURITY_DISPOSAL=77`, `TRANSACTION_CHARGE=33`, `COMMISSION=13`, totals `4` |

Полный page histogram присутствует в safe receipt; его сумма равна `1489`.
Для case inventory доказано:

```text
existing source targets                1783 / 1783
materializable atomic targets          1783 / 1783
duplicate source assertion identities     0
duplicate Gate 3 identities                0
duplicate Gate 4 fact_id                   0
Gate 4 facts without exact Gate 3 match    0
stored relation fields                     0
```

## Изменения и границы

- изменён только Gate 3 role validator для exact known duplicate alias;
- обновлены текущие Role Labeling/authority contracts и generated Gate 1
  closed-world bundle;
- добавлены focused tests для response reordering и duplicated known alias;
- добавлен deterministic G5.84 proof harness;
- provider/model/prompt/Role Pack, Gate 2, decimal normalization, FIFO,
  methodology, metadata/VLM, USER/CASE intake и relations не менялись;
- provider retry, semantic retry, repair, best-of-N и ordinary replay: `0`;
- production visual dependency: `0`.

Verification:

- focused Gate 3/Gate 4/architecture/bundle suite: `144 passed`;
- Role Labeling suite: `17 passed`;
- full frozen replay receipt: `140/140`, provider calls `0`;
- managed asset check: passed;
- dirty tree: `PRESERVE_USER_OWNED`; clean/reset/stage/commit не выполнялись.

Safe receipt:
[G5.84 accounting](./BROKER_REPORTS_PROVIDER_FAILURE_FACT_SET_AND_INVENTORY_G5_84.safe.json).
Exact provider payloads, fact identities, source targets and per-fact rows
остаются вне Git в private evidence.

## Следующий допустимый GOAL

Отдельно определить cross-provider operational policy для случая
`no semantic response`: retryable classes, exact request identity,
idempotency, attempt ceiling, accounting и terminal. Semantic validator
rejection должен остаться `retry=0`. До такого решения G5.84 не разрешает
новый ordinary replay или переход к Gate 5.
