# Broker Reports — Ordinary Trade Release Activation

## Вердикт

`ORDINARY_TRADE_CANDIDATE_RELEASE_QUALIFIED`

Candidate активирован в production только для exact-qualified ordinary
security-trade schemas. Старый semantic route не является runtime fallback.

## Фактически активный pipeline

```text
PDF
→ source-bound table normalization (VLM указывает область, PDFPlumber читает)
→ immutable Canonical
→ exact-fingerprint qualified mapping
→ Source Observations
→ deterministic runtime records
→ Gate 4 Fact v2 compatibility
→ unchanged Gate 5 deterministic consumer
```

Production valves:

```text
ordinary_trade_candidate_enabled = true
ndfl_gate3_enabled = false
```

Unknown fingerprint не получает похожий mapping. Если Canonical отсутствует,
маршрут останавливается с `ordinary_trade_canonical_evidence_missing`; Gate 3
не запускается.

## 102 комиссии

На двух полных реальных supported Canonical проверены все 102
`TRANSACTION_CHARGE`:

- 102/102 amount совпадают с exact Canonical cell и source literal;
- 102/102 связаны с исходным Source Observation и той же table row, что и
  security trade;
- 102/102 имеют ровно один Gate 4 Fact;
- повторно использованных commission source refs: 0;
- повторяющихся charge fact ids: 0;
- сохранённых или придуманных экономических relations: 0.

Связь комиссии со сделкой не угадывается: она существует только там, где
комиссия находится в той же исходной строке сделки. Две комиссии одной строки
остаются двумя разными facts и суммируются Gate 5 один раз каждая.

## Real corpus qualification

| Case | Ready trades | Charges | Unmapped | Gate 5 terminal |
|---|---:|---:|---:|---|
| supported schema A | 45 | 83 | 152 | `gate5_source_fact_acquisition_quantity_insufficient` |
| supported schema B | 15 | 19 | 514 | `gate5_source_fact_acquisition_quantity_insufficient` |
| REPO negative, existing Canonical | 0 | 0 | 173 | fail-closed |

Итого: 899/899 observations accounted, 768/768 runtime values traced, 60
security facts, 102 charges, exact system repeatability `true`, broker/year
profiles `0`, semantic provider calls `0`.

Repeatability включает projection hash, observation ids, runtime records,
Gate 4 fact ids и exact Gate 5 input bytes. Identity semantic decisions не
зависит от порядка model execution. Projection v2 учитывает только реально
совпавшие mappings, поэтому добавление чужой qualified schema не меняет
существующий документ.

## Production smokes

На final server bundle `94a562da…e1cf`:

- supported schema A: 45 ready, 128 runtime records, 152 unmapped;
- supported schema B: 15 ready, 34 runtime records, 514 unmapped;
- в обоих новых cases candidate projection v2 = 1, old semantic artifacts = 0;
- REPO-only PDF на этом live прогоне не получил Canonical от Gate 1 и честно
  остановился до candidate; internal exception устранён, fallback не вызван.

Последний пункт не означает потерю строк candidate-компилятором: candidate не
получил Canonical. На уже проверенном полном Canonical тот же документ сохраняет
173/173 rows как `RELEVANT_UNMAPPED`. Владелец live-ограничения — Gate 1
Canonical admission; оно не расширяет и не блокирует qualified ordinary-trade
scope. Отдельный mixed-table test подтверждает, что unknown table того же
Canonical не блокирует supported table и не превращается в trade.

## Отсутствие старого semantic fallback

- current Gate 3 выключен production valve;
- production composition не вызывает current Gate 3 discovery, second role
  pass или `Gate4FinancialCaseRuntimeFactory`;
- candidate Gate 4 adapter не импортирует Gate 3 runtime;
- в новых production cases нет `FinancialAnnotationsV1/V2` и old Gate 4
  semantic artifacts;
- whole-deployment rollback существует и доказан, semantic fallback отсутствует.

## Release и rollback

- active source revision: `e3fd71f17047f18f7dcc13c22ad0efd0b975a6ec`;
- release id: `broker-reports-e3fd71f17047`;
- manifest SHA-256: `fd1518df4d1afb47a523cbba4858c55bb82d21c1c1af02c87b0e768bd1a7fca9`;
- bundle SHA-256: `94a562dad4c9728c0e6dca4777070644ec1fbc4b63d1c7634ad9a7f25846e1cf`;
- rollback identity: `021f3170c3769ac997245cb0b084a8912d248b20bfa9d209c797aeb8a6aea0ce`;
- rollback proof: previous state restored, candidate state restored, loader states
  restored;
- final readback: bundle, revision, valves, rollback identity, workload
  quiescence and staging cleanup — pass.

## Test ownership

- full service run before the final narrow fail-closed fix: 3842 passed, 5
  skipped, 2 bundle failures and 25 errors;
- both bundle failures belonged to this release and were fixed by rebuilding all
  three bundles; their exact parity tests pass;
- 25 errors share historical frozen-proof authority pins for previously changed
  provider/architecture sources. These inactive research builders are not
  imported or read by the active candidate route and were not rewritten;
- final candidate/release/bundle set, including mixed-boundary behavior: 43/43
  pass; Ruff pass.

`pdf_table_locator_provider.py` is now registered in the architecture owner
allowlist. Windows byte-exact bundle rebuild passes after rebuilding every
generated bundle. No release blocker remains inside the qualified scope.
