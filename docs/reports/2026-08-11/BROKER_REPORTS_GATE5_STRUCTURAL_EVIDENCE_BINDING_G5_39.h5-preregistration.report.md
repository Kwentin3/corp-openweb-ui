# G5.39 H5 preregistration — deterministic exact-key closure

Status: `FROZEN_BEFORE_H5_INFERENCE`
Experiment commit: `f7fc8be01b97e275a0ebf001b0323c686205bf66`
H5 config SHA-256: `f80a48777c367c65e2566125e84ebe38c7aa20df86e1cdeb9fd05e20a6778c72`

H5 is added because H4 produced a substantive new alternative, not a cosmetic prompt variant: model-directed page navigation selected a wrong large-document section and an over-wide set, while the source rows already contained exact repeated identity/date/order literals. H5 moves candidate selection authority from the model to a deterministic exact-literal index.

## Frozen H5 contract

```text
accepted anchor row
  -> exact source-literal / explicit-relation index
  -> bounded two-hop equality closure (max 24 rows)
  -> one model pass inside that closed row set
  -> closed exact-ref evidence bundle
```

Selection uses no semantic query, broker name, template, taxonomy prediction or expected oracle. Explicit source relations override equality expansion. Otherwise, first-hop rows must share an exact date or at least two exact non-trivial literals with the anchor; second-hop rows must share at least two such literals with a selected row. Deterministic inverse-frequency ordering and source order break ties. The anchor is never dropped; tail rows are deterministically removed only to meet the frozen budget.

## Frozen H5 budget and evaluation

- Same corpus v3, oracle, common baseline, provider/model, temperature, hard invariants and lexicographic winner rule as preregistration v3.
- Provider calls per case: at most `1`.
- Deterministic retrieval rounds per case: `1`.
- Total input: at most `16,000` chars; output: at most `1,800` tokens.
- Retrieved structural content: at most `10,000` chars.
- Retry / repair / best-of-N / answer merge: `0 / 0 / false / false`.
- The A/B fixture must use its explicit order relation and reject every mixed event.
- H5 must pass DEV, independent holdout, large-context pressure, hard invariants and downstream compatibility to win.

No algorithm threshold or token rule may change after H5 output. If H5 fails, the tournament terminal is `NO_STRATEGY_PROVEN`; no H6 will be added in this GOAL.
