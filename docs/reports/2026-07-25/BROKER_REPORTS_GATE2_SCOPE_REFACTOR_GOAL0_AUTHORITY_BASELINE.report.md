# Broker Reports — Gate 2 deterministic scope refactoring, Goal 0: authority baseline

Дата: 2026-07-25  
Статус: `COMPLETED`  
Accepted base revision: `28f8d0106de99f54041df1ceab15516a80c4fd67`  
Branch: `codex/broker-reports-gate2-scope-refactor-goal0-baseline`  
Delivery PR: `#126`

## Итог

Implementation baseline зафиксирован без изменения production, stage или
контрактов. Repository authorities, live stage state и исторический frozen
full-scope baseline разделены явно.

Acceptance:

- `AUTHORITIES: PINNED`;
- `STALE_RECEIPTS: ZERO`;
- `REPOSITORY_STAGE_BOUNDARY: EXPLICIT`;
- `PRODUCTION_CHANGE: ZERO`.

## Repository boundary

- `local main` при старте:
  `28f8d0106de99f54041df1ceab15516a80c4fd67`;
- `origin/main`:
  `28f8d0106de99f54041df1ceab15516a80c4fd67`;
- divergence: `0 0`;
- canonical worktrees: `1`;
- предыдущий research delivery: PR #125, merge
  `28f8d0106de99f54041df1ceab15516a80c4fd67`.

## Frozen semantic authorities

| Authority | Version | Semantic identity |
|---|---|---|
| Financial Evidence Registry | `broker_reports_gate2_financial_evidence_registry_v1`, 2 declarations | `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8` |
| Financial decision | `broker_reports_gate2_financial_evidence_decision_v1` | Git-blob SHA-256 `dc4fd160...f19f` |
| Financial materializer | existing deterministic factory | Git-blob SHA-256 `76689086...e41ef` |
| Financial context | `broker_reports_gate2_financial_context_v1` | Git-blob SHA-256 `3207337c...41472` |
| Checksum | Gate 2-only checksum contract | Git-blob SHA-256 `dbe1d83d...a3d8` |
| Economy model policy | `1.4.0`, `broker_reports_economy_model_policy_v2` | `e71bbb7c95774058bc2324343a2de2adef2f3307d8b30f8e92d8cbf514bd09c9` |
| Workload policy | `1.4.0`, `broker_reports_gate2_economy_workload_policy_v2` | `f1eb7daa08f10c125d21addb5ec03a5dfac42207cc39a4b3aa86224820fc3a7d` |
| Qualification registry | `broker_reports_gate2_economy_workload_qualification_v2`, 16 entries | `9a5923d61bf8ca73db2ce6acc37e9c2ea85d2c197625f15469b6cac5dae54c23` |

Четыре disposition заморожены:

- `typed_input`;
- `unclassified_financial_input`;
- `no_financial_input`;
- `unsupported`.

Новый model-facing source/domain contract в этой программе не создаётся.

## Canonical repository file identities

SHA-256 вычислен по exact Git blob, а не по checkout с платформенной
нормализацией строк.

| Boundary | File | Git blob SHA-256 |
|---|---|---|
| Gate 1 values/provenance | `gate1_public_contracts.py` | `6ad32dd8fe7e88ec77f852a70eb3abdfafb82927b9bd497651380ebb5a0fe227` |
| Gate 1→Gate 2 readiness | `gate2_input_readiness.py` | `ff14f4a00ef0fc4397b42655cb8cf43f93b3451738aa34aa0b88d5d64b7f99b5` |
| legacy source schema | `gate2_source_fact_contracts.py` | `1bac3be29d76df354131b5b7c4189dc1b1d16aa9131aabc5121fef6b33b20bc3` |
| deterministic segmentation | `gate2_source_unit_segmentation.py` | `68cc3bbb3b6e9c0df4b2b8866c35785aab6299156a8fd3dfeb0173544c1257d1` |
| deterministic router | `gate2_domain_routing.py` | `34a54d658bca3210eac51e484ff5bf3f58de83dfeae361ea4ea26a533f1cc127` |
| deterministic package builder | `gate2_domain_packages.py` | `dc9091cea7986a9c18bb3a1668013e57302fc278864eef4ceb6e6e1bfc1bad52` |
| source package authority | `gate2_financial_evidence_source_package.py` | `b8903ff3bd67613fbc0d808bfe71c439479a840a77857aec5e596cde25686413` |
| Registry | `gate2_financial_evidence_registry.py` | `e5f3d67a0a71f8031577854d548e56019eca6b3ab20f315519d79b8b721883da` |
| decision | `gate2_financial_evidence_decision.py` | `dc4fd160aeda35b2d0a3d063a871d4cc71f6efcefcc134d0d164722d5176f19f` |
| materialization contracts | `gate2_financial_evidence_materialization_contracts.py` | `723aec7612e416c611f6813099db1453367a2b4b6246e5ce3f6dbdf05cb1b4a0` |
| materializer | `gate2_financial_evidence_materialization.py` | `7668908631897ae106c3bde18825070ccd50738b557237c9c299977ba2de41ef` |
| compatibility reader | `gate2_financial_evidence_compatibility.py` | `7603162e4693b9440a7de78df3446189a59b03a1624a863daab09666b0118b50` |
| legacy validator | `gate2_financial_evidence_legacy_validation.py` | `9f01966e6ae4e3ed7255fa872622e1def80db3636f9149c3d07cb947ed071919` |
| context contracts | `gate2_financial_context_contracts.py` | `e6c08d4a121f751029ace7239e4d2adbf851b3fdcde35e514505e49dde049b66` |
| context projection | `gate2_financial_context.py` | `3207337cb2c64774c05a19a410dbf0dc8d734d53798215d02b8d0461a5e41472` |
| checksum | `gate2_financial_context_checksum.py` | `dbe1d83dbb60ffc8c710ff69e4eb5b57fec330d93f7902c4c326aef987f1a3d8` |

## Frozen full-scope product baseline

Baseline authority:
`BROKER_REPORTS_GATE2_GOAL7_FULL_SCOPE_SHADOW_QUALIFICATION.receipt.safe.json`,
Git-blob SHA-256
`9b2990f59972caa1f3dde920d180ab17d38f4d6b65ba22a797e3beff20dd5288`.

| Invariant | Frozen value |
|---|---:|
| documents | 1 |
| parent units | 12 |
| derived segments | 210 |
| domain packages | 41 |
| canonical scopes | 39 |
| selected source refs | 455 |
| accounted source refs | 455 |
| uncovered refs | 0 |
| excess refs | 0 |
| duplicate interpretations | 0 |
| ownership conflicts | 0 |
| contradictory decisions | 0 |
| unclassified value retention | 147/147, 100% |
| fallback / hidden repair | 0 / 0 |

Это frozen product baseline, а не доказательство current stage parity.
Исторический legacy rollback baseline внутри того же receipt — `448/455` и
7 uncovered refs — не принимается как successor target.

## Exact economy references

- GPT-5.4 Nano financial receipt: `QUALIFIED_4_OF_4`;
- exact model: `gpt-5.4-nano-2026-03-17`;
- authorization:
  `efde8a286bc93d62b1983793d3c4d4bc5948c649b2390b3075dd3365bff3e012`;
- Haiku checksum receipt: `QUALIFIED_3_OF_3`;
- exact model: `claude-haiku-4-5-20251001`;
- authorization:
  `45d955c6ef0d4270cbb82b587bcadb6f7adf2faf55e1453fb5d25ccd507ce610`.

Read-only live preflight на 2026-07-25:

- `/api/models`: 42 published models;
- Nano exact ID: published;
- Haiku exact ID: published;
- qualification action: active, exact, qualification-only;
- provider calls: 0.

## Current live stage boundary

Read-only verifier запущен против accepted base. Status ожидаемо `failed`
только из-за repository/live Function bundle parity. Stage не изменялся.

| Function | Live SHA-256 | Repository SHA-256 | Exact |
|---|---|---|---|
| `broker_reports_gate1_pipe` | `a042ff14...70519` | `8fbcfbc9...6d94` | no |
| `broker_reports_gate2_source_fact_pipe` | `d3ba38ed...d503` | `2b7a34b9...b56a` | no |
| `broker_reports_gate2_domain_source_fact_pipe` | `4f5424f2...bb0d5` | `4e68f73e...b17e` | no |

Live-safe valves:

- source `semantic_selection_enabled=false`;
- domain `candidate_binding_enabled=false`;
- domain `financial_evidence_enabled=true`;
- domain Registry version exact v1;
- domain `max_repair_attempts=1`;
- Gate 3 context manifest disabled;
- answer context selection enabled.

Other stage findings:

- three Functions active and non-global;
- valves match current expected configuration;
- managed prompts: 12/12 exact;
- private intake action: exact;
- factory boundary checks: passed;
- workload quiescent; owned temp entries: 0;
- stage release identity: composite/stale relative to current repository;
- current repository release candidate ID:
  `broker-reports-28f8d0106de9`;
- stage mutations in Goal 0: 0.

Следовательно, будущий release нельзя объявлять repository/live exact до
отдельного atomic release Goal. Goal 1 остаётся repository-only.

## Immutable compatibility policy

- persisted legacy artifacts не переписываются;
- legacy readers и validators сохраняются;
- successor schema получает новую explicit identity;
- silent upcast запрещён;
- FNS specialized path остаётся отдельным;
- rollback меняет только future routing после admission.

## Verification

- contracts changed: `0`;
- contracts explicitly unchanged: Registry, financial decision, materializer,
  context v1, checksum, legacy readers;
- provider calls: `0`;
- customer calls: `0`;
- stage mutations: `0`;
- production routing changes: `0`;
- customer values/raw provider output in Git: `0`;
- focused authority/stage tests: `152 passed in 6.76s`;
- full Broker Reports suite:
  `1400 passed, 20 skipped, 5 warnings in 92.34s`;
- privacy: `PASSED`.

## Next permitted Goal

После merge этого PR разрешён только Goal 1:
pure deterministic financial scope authority. Он не меняет production
routing, не делает provider calls и стартует от нового `origin/main`.
