# Broker Reports Gate 2 — Context V2.1 GOAL 13 post-smoke forensic audit

- Status: `completed`
- Cases inspected: `3`
- Provider calls: `0`
- Runtime, product logic, Prompt, Context and expected-answer changes: `0`
- Corrective implementation: `0`
- Full benchmark: `not run`
- Context V2.1 active: `false`
- Production admissions: `[]`

## Verdict

All three model outputs preserved the safe
`unclassified_financial_input` disposition. Each failure is confined to the
diagnostic reason and, mechanically, to the declared count of plausible
distinct types:

| Case | Independently audited count | Count asserted by returned reason |
| --- | --- | --- |
| Nano `syn_successor_v2_multiple_compatible` | `2+` | `1` |
| Nano `syn_successor_v2_detail_vs_subtotal` | `1` | `0` |
| Haiku `syn_successor_v2_no_registry_type` | `0` | `2+` |

This proves the error locus, not its root cause. Choices presentation is a
supported risk in all three cases. Flat source association is a supported risk
for `multiple_compatible` and a hypothesis for `detail_vs_subtotal`. The
minimal glossary's omission of the full managed detail-row exclusion is a
supported risk for the Haiku case. Model capability remains a hypothesis.
Independent revalidation does not support an expected-answer defect.

No result in this audit is unsafe typing, and the audit does not choose or
implement a refactor.

## Evidence boundary

The exact inspected input/output is the immutable GOAL 12
[transparent synthetic evidence](../2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.transparent.json):

- raw file SHA-256:
  `7f4718f13763c9963592326e8481072606219435495fb6fbd59655a881197281`;
- canonical report integrity:
  `e4b2ed6e0da8c58b4236aabf0e009c957b3d1fbdfa593fed81f32c6dac5ccef5`;
- frozen plan integrity:
  `9191197bdc947d6ba86db3169ba0d8c911ef88423d611e2c4424a9379167cbab`.

Both GOAL 13 evidence files are pinned to `text eol=lf` in
`.gitattributes`, so the raw report SHA-256 is stable across checkouts.

Expected answers were revalidated without using model answers against:

- the frozen
  [successor fixture](../../../services/broker-reports-gate1-proof/benchmarks/gate2_financial_successor_v2/manifest.json);
- the additive
  [outcome-audit manifest](../../../services/broker-reports-gate1-proof/benchmarks/gate2_financial_semantic_v6_outcome_audit_v1/manifest.json),
  raw SHA-256
  `6c303dee2c8d221e452a565c0da2c1dae6d00b609054e6eacfa42f497d71432d`
  and canonical integrity
  `774acd03c95ddc2d898112b6b62e3bed54613cfeaac7f98689e7c05224d271ae`;
- the
  [Financial Semantic Pack](../../../services/broker-reports-gate1-proof/semantic_packs/broker_reports_financial_semantic_pack.v1.json),
  raw SHA-256
  `9538ccb8f2111efa24e25d1b7b10145ccff8ca4e3c655cdc6d71b916d926c3fd`
  and canonical integrity
  `ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`;
- the managed
  [reason catalog v2](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v2.json),
  raw SHA-256
  `fb1adbc8cdb69096d3a40de3418392215560ce980b23a95d3f1fb48e66429289`
  and canonical integrity
  `2510b57b51749a14f76b987cddaa3eea19f1bb975a97c6c089565253dc3593e9`;
- the versioned
  [outcome taxonomy](../../stage2/contracts/BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md).

Historical GOAL 12 evidence and benchmark manifests were not changed. This is
an analysis-only successor report.

Evidence strength is used as follows:

- `proven`: directly present in immutable evidence or follows from a closed
  authority mapping;
- `supported`: evidence makes the layer a concrete contributor risk but does
  not establish causation;
- `hypothesis`: possible explanation not established by the available output.

## Exact shared model-visible type cards

The following array is `TC-1`. It is byte-identical inside the exact user
content of all three inspected requests:

```json
[{"type_key":"type_1","title":"Cash balance snapshot","definition":"A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.","positive_signal":"A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.","negative_signal":"A synthetic row states a segregated regulatory asset without an ordinary cash classification.","nearest_competitor":{"type_key":"type_2","distinction":"Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified."}},{"type_key":"type_2","title":"Printed financial metric","definition":"A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.","positive_signal":"A synthetic statement prints a labelled total for an explicit period and statement scope.","negative_signal":"A total calculated by Gate 2 from child rows.","nearest_competitor":{"type_key":"type_1","distinction":"A printed total is not a cash balance unless ordinary cash-class state semantics are explicit."}}]
```

The common exact system message was:

```text
Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.
```

The common exact visible reason cards were:

```json
[{"code":"no_registry_type","title":"No available type matches","use_when":"Source-stated financial values are present, but none of the available financial type definitions matches their visible meaning."},{"code":"single_registry_type_no_safe_record","title":"One matching type, no safe record","use_when":"Exactly one available financial type remains plausible, but the visible source does not uniquely support one complete prebound record for that type."},{"code":"ambiguous_registry_type","title":"Multiple available types remain plausible","use_when":"Source-stated financial values are present and two or more distinct available financial type definitions remain plausible after all visible evidence is considered, so no single type can be selected safely."}]
```

## Case 1 — Nano `syn_successor_v2_multiple_compatible`

Source GOAL 12 case integrity:
`b0ecca88a5e18b58b8530200afb91001c5dca89c7a91c341bd4c4956cd3d80b3`.

| Required field | Exact finding |
| --- | --- |
| Exact source facts | `{"children":[{"kind":"table","children":[{"kind":"row","values":[{"meaning":"amount a","literal":"310.00"},{"meaning":"amount b","literal":"410.00"},{"meaning":"description","literal":"Possible cash"},{"meaning":"currency","literal":"EUR"},{"meaning":"as of date","literal":"2026-03-03"},{"meaning":"description 2","literal":"Possible total"}]}]}]}` |
| Exact visible type cards | `TC-1`, reproduced exactly above; `type_1=Cash balance snapshot`, `type_2=Printed financial metric`. |
| Exact visible choices | `[]` |
| Exact adapter-extracted model answer | `{"choice":"unclassified","reason":"single_registry_type_no_safe_record"}` |
| Normalized answer | `{"disposition":"unclassified_financial_input","reason_code":"single_registry_type_no_safe_record"}` |
| Audited expected answer | `{"disposition":"unclassified_financial_input","reason_code":"ambiguous_registry_type"}` |
| Reasonably plausible types | `cash_balance_snapshot_v1`; `printed_financial_metric_v1` |
| What the model likely understood correctly | Technical schema conformance is `proven`. Because the response schema exposed only the unclassified branch, semantic understanding of the safe disposition is not proven. Its reason at least asserts that no safe complete typed record exists, but this interpretation is only `supported`. |
| Exact misclassification | The reason declared exactly `1` plausible type where the audited set has `2+`: `2+ → 1`. The disposition matched; only `reason_code` differed. |

Independent revalidation: `Possible cash` keeps the cash snapshot type
plausible, while `Possible total` keeps the printed metric type plausible.
They are distinct managed types. No complete typed choice is safe. The closed
truth table therefore maps `2+ plausible / 0 safe` to
`ambiguous_registry_type`, not
`single_registry_type_no_safe_record`.

| Possible error layer | Evidence strength | Classification |
| --- | --- | --- |
| Source projection | `supported` | Both labels and both amounts survive, so source loss is not shown. They remain flat sibling values without visible pair grouping; this is a concrete association risk. Its causal effect is unobserved. |
| Type glossary | `hypothesis` | Both relevant cards and their reciprocal distinction are visible. The response does not reveal which type, if any, Nano discarded. |
| Choices presentation | `supported` | `choices=[]` and a schema-forced unclassified branch are proven. Zero safe choices could be mistaken for a one-type/no-record state, but causation is not observable. |
| Reason contract | `proven` | The only failing output field is the model-owned reason, whose closed meaning declares type-cardinality `1` instead of `2+`. This proves the locus, not that the contract caused the mistake. |
| Model capability | `hypothesis` | One answer without a rationale or plausible-type set cannot isolate model capability from presentation effects. |
| Expected-answer defect | `hypothesis` | Not supported: source, Pack, outcome-audit manifest and closed truth table independently reproduce `2+ / 0 → ambiguous_registry_type`. |

## Case 2 — Nano `syn_successor_v2_detail_vs_subtotal`

Source GOAL 12 case integrity:
`882863401f598c8dec414e5f92dc8fe7b524e6e96bee775bb8b6616d75636953`.

| Required field | Exact finding |
| --- | --- |
| Exact source facts | `{"children":[{"kind":"table","children":[{"kind":"row","values":[{"meaning":"currency","literal":"USD"},{"meaning":"date","literal":"2026-03-06"},{"meaning":"detail amount","literal":"25.00"},{"meaning":"description","literal":"Fee detail and subtotal"},{"meaning":"subtotal amount","literal":"125.00"}]}]}]}` |
| Exact visible type cards | `TC-1`, reproduced exactly above; `type_1=Cash balance snapshot`, `type_2=Printed financial metric`. |
| Exact visible choices | `[]` |
| Exact adapter-extracted model answer | `{"choice":"unclassified","reason":"no_registry_type"}` |
| Normalized answer | `{"disposition":"unclassified_financial_input","reason_code":"no_registry_type"}` |
| Audited expected answer | `{"disposition":"unclassified_financial_input","reason_code":"single_registry_type_no_safe_record"}` |
| Reasonably plausible types | `printed_financial_metric_v1` only |
| What the model likely understood correctly | Technical schema conformance is `proven`. Because the response schema exposed only the unclassified branch, semantic understanding of the safe disposition is not proven. Recognition that no ready typed record can be selected is at most `supported`. |
| Exact misclassification | The reason declared `0` plausible types where the audited set has exactly `1`: `1 → 0`. The disposition matched; only `reason_code` differed. |

Independent revalidation: the source has no ordinary cash-class semantics, so
the cash type is ruled out. Its labelled subtotal keeps the printed metric type
plausible. The distinct detail and subtotal amounts do not support one unique
complete prebound record. The closed truth table therefore maps
`1 plausible / 0 safe` to `single_registry_type_no_safe_record`.

| Possible error layer | Evidence strength | Classification |
| --- | --- | --- |
| Source projection | `hypothesis` | No literal is lost and `detail amount` is visibly distinct from `subtotal amount`. The combined flat row may still make their association harder to read, but causation is not established here. |
| Type glossary | `hypothesis` | The visible printed-metric definition and positive signal cover a labelled source total, and cash semantics are absent. No specific glossary defect is shown. |
| Choices presentation | `supported` | `choices=[]` proves zero safe prebound records, not zero plausible types. The surface does not separately expose that distinction except through reason wording. |
| Reason contract | `proven` | The only failing output field is the reason, which declares cardinality `0` instead of `1`. This proves the locus, not a contract root cause. |
| Model capability | `hypothesis` | Confusing `0/0` with `1/0` is consistent with a capability limit, but one response cannot prove it. |
| Expected-answer defect | `hypothesis` | Not supported: the corrected frozen outcome audit and independent source/Pack/taxonomy derivation reproduce `1 / 0 → single_registry_type_no_safe_record`. |

## Case 3 — Haiku `syn_successor_v2_no_registry_type`

Source GOAL 12 case integrity:
`71493ed9f00b8702643c50b22e3252bd1bc1ddcf7e389bd94141d3dac4b4629b`.

| Required field | Exact finding |
| --- | --- |
| Exact source facts | `{"children":[{"kind":"table","children":[{"kind":"row","values":[{"meaning":"amount","literal":"42.25"},{"meaning":"currency","literal":"CHF"},{"meaning":"date","literal":"2026-03-04"},{"meaning":"description","literal":"Broker fee detail"}]}]}]}` |
| Exact visible type cards | `TC-1`, reproduced exactly above; `type_1=Cash balance snapshot`, `type_2=Printed financial metric`. |
| Exact visible choices | `[{"choice_key":"choice_1","title":"Printed financial metric"},{"choice_key":"choice_2","title":"Cash balance snapshot"}]` |
| Exact adapter-extracted model answer | `"{\"choice\":\"unclassified\",\"reason\":\"ambiguous_registry_type\"}"` |
| Normalized answer | `{"disposition":"unclassified_financial_input","reason_code":"ambiguous_registry_type"}` |
| Audited expected answer | `{"disposition":"unclassified_financial_input","reason_code":"no_registry_type"}` |
| Reasonably plausible types | None: `[]` |
| What the model likely understood correctly | It refused both visible typed choices; that output fact is `proven` and supports, but does not prove, an understanding that no complete typed record was safe. |
| Exact misclassification | The reason declared `2+` plausible types where the audited set is empty: `0 → 2+`. The disposition matched; only `reason_code` differed. |

Independent revalidation: `Broker fee detail` is not an ordinary cash-class
balance. The full managed Pack also states that a detail row is not a printed
metric unless the source explicitly presents it as a labelled metric or total.
This source does neither. The plausible type set is therefore empty, and the
truth table maps `0 / 0` to `no_registry_type`. Reason catalog v2 uses this
exact synthetic source as its positive example and explicitly warns that
structurally generated typed options may still exist.

| Possible error layer | Evidence strength | Classification |
| --- | --- | --- |
| Source projection | `hypothesis` | All four source facts survive in one simple row. No source loss or association ambiguity capable of creating two meanings is shown. |
| Type glossary | `supported` | The full Pack's directly relevant detail-row exclusion is absent from `TC-1`; the minimal card exposes only the selected definition, first example, first counterexample and nearest-current-type rule. This is a concrete omission, but its causal effect is unobserved. |
| Choices presentation | `supported` | Two structural typed choices are visible even though the independently audited plausible-type set is empty. Equating visible choice count with plausible-type count would yield the returned reason exactly, but the output does not reveal Haiku's reasoning. |
| Reason contract | `proven` | The only failing field is the model-owned reason, which declares cardinality `2+` instead of `0`. This proves the locus, not a contract root cause. |
| Model capability | `hypothesis` | A capability limitation is consistent with the answer but cannot be separated from the two supported presentation risks using this output alone. |
| Expected-answer defect | `hypothesis` | Not supported: the source, full Pack, closed audit mapping and exact managed positive example independently reproduce `0 / 0 → no_registry_type`. |

## Cross-case conclusion

The exact forensic result is:

1. `3/3` safe unclassified dispositions;
2. `3/3` wrong diagnostic reasons;
3. `0` unsafe typed outputs and `0` wrong typed types;
4. `3/3` errors mechanically classified as plausible-type-cardinality errors;
5. `0` proven causal root layers.

The response contract does not expose a rationale or an explicit plausible-type
set, so it cannot tell which type a model retained or rejected. That
observability limit prevents a proven choice among source projection, glossary,
choices presentation and model capability. GOAL 13 therefore stops at
classification. It does not start GOAL 14, run a full benchmark, alter an
expected answer or implement the later preferred refactor.

The adjacent
[privacy-safe receipt](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_GOAL13.receipt.safe.json)
contains bounded case identities, hashes, classifications and zero-call/change
accounting.
