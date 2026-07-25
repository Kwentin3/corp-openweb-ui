# Broker Reports — Gate 2 v4, Goal 4: GPT-5.4 Nano financial requalification

Дата: 2026-07-25

Статус: `COMPLETED`

## Результат

`gpt-5.4-nano-2026-03-17` формально квалифицирован для exact workload
`gate2_financial_evidence` на текущих policy/contract revisions.

Terminal result:

- `GPT_5_4_NANO_FINANCIAL: QUALIFIED_4_OF_4`;
- `FREE_FORM_TYPE_IDS: ZERO`;
- `REPAIR: ZERO`;
- `FALLBACK: ZERO`.

Все четыре frozen synthetic dispositions совпали:

| Case | Expected | Observed | Canonical | Materialization |
|---|---|---|---|---|
| typed | `typed_input` | `typed_input` | passed | passed |
| unclassified | `unclassified_financial_input` | `unclassified_financial_input` | passed | passed |
| no financial | `no_financial_input` | `no_financial_input` | passed | passed |
| unsupported | `unsupported` | `unsupported` | passed | passed |

Qualification не активирует production admission. Выбор production matrix
остаётся Goal 10.

## Git

- accepted execution revision:
  `34f440b0339024217e9b4fac3f98c08809504265`;
- branch:
  `codex/broker-reports-gate2-v4-goal4-gpt54-nano-financial-requalification`;
- PR: будет закреплён после открытия evidence-only PR.

## Exact qualification identity

| Contract | Revision |
|---|---|
| exact model | `gpt-5.4-nano-2026-03-17` |
| workload | `gate2_financial_evidence` |
| provider profile | `openai_gpt` |
| provider route | `openwebui_0.9.6_maintained_route_2026-07-24` |
| input | `broker_reports_gate2_financial_evidence_source_package_v1` |
| output | `broker_reports_gate2_financial_evidence_decision_v1` |
| prompt | `gate2_financial_evidence_shadow_prompt_v1` |
| adapter | `gate2_openai_response_format_adapter_v1` |
| canonical validator | `sha256:747d83552f394f4bd56249820e9630adc97a4d2435da60cbd9b2b376685eb5be` |

Authorization identity:
`efde8a286bc93d62b1983793d3c4d4bc5948c649b2390b3075dd3365bff3e012`.

Policy:

- model policy `1.4.0`:
  `e71bbb7c95774058bc2324343a2de2adef2f3307d8b30f8e92d8cbf514bd09c9`;
- workload policy `1.4.0`:
  `f1eb7daa08f10c125d21addb5ec03a5dfac42207cc39a4b3aa86224820fc3a7d`;
- qualification policy:
  `d6b33ce5bdfd5e75b6c6afb66efa47a79150144c522f8e2ea433a7a045c23395`;
- reasoning: `disabled`;
- paid tools: `false`.

## Contract checks

Canonical validation and deterministic materialization passed `4/4`.
Therefore the unchanged authority confirmed:

- typed case uses Registry-bound
  `printed_financial_metric_v1`;
- required roles are complete;
- bindings use allowed source refs only;
- unclassified case has no invented canonical type;
- no-financial case has no value bindings;
- unsupported case remains explicit;
- model does not provide system-owned lineage/execution fields;
- strict schema output only;
- requested and resolved exact model IDs match.

Provider schema projection:

| Case | Canonical/adapted schema SHA-256 | Transforms |
|---|---|---:|
| typed | `978f10d97f733f289b9935c155c74731161f38a000977dd7c5045565a7a28ec7` | 0 |
| unclassified | `3b4a6204d15acee98c444eb5a196ee023e78e53d0dee1b223f39e7b5d9f11a42` | 0 |
| no financial | `c029308ae2daef491535649f97a3de6926621b7f918864944f7dc953ea7d0226` | 0 |
| unsupported | `faf835890c9357666fce765cc8e06be0aa87bbaf45abd02ac54847f71bea3170` | 0 |

## Usage and cost

| Case | Input | Output | Total | Actual USD |
|---|---:|---:|---:|---:|
| typed | 1309 | 110 | 1419 | 0.000399300 |
| unclassified | 555 | 57 | 612 | 0.000182250 |
| no financial | 558 | 34 | 592 | 0.000154100 |
| unsupported | 556 | 32 | 588 | 0.000151200 |
| **Total** | **2978** | **233** | **3211** | **0.000886850** |

Дополнительно:

- provider calls: `4`;
- finish reason `stop`: `4/4`;
- strict JSON schema: `4/4`;
- reasoning tokens: `0`;
- cached input tokens: `0`;
- total provider duration: `10063 ms`;
- private safe receipt SHA-256:
  `9fceb00ae306f3e11064c423dc1721f949c11c98833febfee939d25f142918fb`.

## Aggregate accounting

- provider calls: `4`;
- customer calls: `0`;
- input tokens: `2978`;
- output tokens: `233`;
- actual cost: `USD 0.000886850`;
- expensive model calls: `0`;
- fallback calls: `0`;
- repair attempts: `0`;
- paid tools: `0`;
- stage mutations: `0`;
- Knowledge/RAG/vector writes: `0`;
- Gate 3 executions: `0`.

## Contracts changed

`ZERO`.

Goal 4 добавляет только safe report/receipt. Runtime, Registry, prompt,
schema, validator и stage не менялись.

## Contracts explicitly unchanged

- Financial Evidence Registry;
- four-disposition decision contract;
- deterministic materializer;
- financial context projection;
- checksum comparator;
- provider adapter/route;
- production workload routing/admissions;
- Gate 1 visual behavior;
- stage Functions/Pipes/Prompts;
- Knowledge/RAG/vectorization;
- Gate 3.

## Tests

- focused: `104 passed in 1.18s`;
- full: `1395 passed, 20 skipped, 5 existing warnings in 90.48s`;
- preflight: passed, provider calls `0`;
- live stderr bytes: `0`.

## Privacy

`PASSED`.

- synthetic non-customer fixtures only;
- customer corpus read: `false`;
- raw provider output in Git: `false`;
- full safe receipt remains under ignored `local/`;
- committed receipt contains only safe accounting/contract evidence;
- secrets in Git: `false`.

## Next permitted goal

Goal 5 after merge:

- execute Gemini 3.5 financial secondary on the same four dispositions;
- narrow Gemini 3.1 prior-failure localization only;
- no production admission.
