# Broker Reports — Gate 2 v4 Goal 0: final authority baseline

Дата: 2026-07-25

Статус: `COMPLETED_WITH_EXPLICIT_GAPS`

## Итог

Новый baseline построен с принятого `main`, после merge PR #110 и #111.
Repository authorities и фактическое состояние stage закреплены раздельно.
Stage не изменялся.

Acceptance:

- `CURRENT_AUTHORITIES: PINNED`;
- `STALE_RECEIPTS_USED_AS_CURRENT: ZERO`;
- `REPOSITORY_STAGE_BOUNDARY: EXPLICIT`;
- `PRODUCTION_ALLOWLIST: EMPTY`;
- `STAGE_MUTATIONS: ZERO`.

Явный gap: stage имеет composite Function identity. Gate 1 и source
соответствуют release tree `efee1fe`, но live domain Function соответствует
принятому repository commit `b3f381b`, а его release metadata всё ещё
содержит старый bundle hash. Поэтому stage нельзя описывать одним exact
release revision или старым manifest receipt.

## Git authority

- audited accepted-main revision:
  `54364a4c4805badca4984533f55fcbfc00ee055e`;
- `origin/main`:
  `54364a4c4805badca4984533f55fcbfc00ee055e`;
- branch:
  `codex/broker-reports-gate2-v4-goal0-final-authority-baseline`;
- divergence from `origin/main` before report commit: `0 0`;
- canonical worktrees: `1`;
- PR #110 merge:
  `0e1bb9ac2d72776cabb4377f82d98dcaa905c02e`;
- PR #111 merge:
  `54364a4c4805badca4984533f55fcbfc00ee055e`.

## Frozen repository authorities

Semantic authorities:

| Authority | Version/schema | Semantic hash |
|---|---|---|
| Financial Evidence Registry | `broker_reports_gate2_financial_evidence_registry_v1` | `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8` |
| Economy model policy | `1.4.0`, `broker_reports_economy_model_policy_v2` | `e71bbb7c95774058bc2324343a2de2adef2f3307d8b30f8e92d8cbf514bd09c9` |
| Workload policy | `1.4.0`, `broker_reports_gate2_economy_workload_policy_v2` | `f1eb7daa08f10c125d21addb5ec03a5dfac42207cc39a4b3aa86224820fc3a7d` |
| Qualification registry | `broker_reports_gate2_economy_workload_qualification_v2`, 16 subjects | `9a5923d61bf8ca73db2ce6acc37e9c2ea85d2c197625f15469b6cac5dae54c23` |

Canonical Git-blob SHA-256 from accepted `main`:

| Authority file | Git-blob SHA-256 |
|---|---|
| Financial Evidence Registry | `e5f3d67a0a71f8031577854d548e56019eca6b3ab20f315519d79b8b721883da` |
| four-disposition decision contract | `dc4fd160aeda35b2d0a3d063a871d4cc71f6efcefcc134d0d164722d5176f19f` |
| deterministic materialization | `7668908631897ae106c3bde18825070ccd50738b557237c9c299977ba2de41ef` |
| financial context projection | `3207337cb2c64774c05a19a410dbf0dc8d734d53798215d02b8d0461a5e41472` |
| checksum contract/comparator | `dbe1d83dbb60ffc8c710ff69e4eb5b57fec330d93f7902c4c326aef987f1a3d8` |
| economy model policy | `c85db6f738ab48bcc5dcdd1214af82d23f18b0bd6de2900bc033bd453b69da05` |
| workload policy | `0dee6f2d0fa757288cd193d06e2fbfbd2015fbf35695ece7710ae6ee0e8c3092` |
| qualification registry | `353ff899279ce9936d7349070ac90db82a951c8ced0703ae0830859603c2a882` |

Git-blob hashes используются как platform-neutral repository identity.
Checkout byte hashes, зависящие от CRLF normalization, не используются как
новая semantic authority.

## Repository workload state

Разрешены только:

- `models/gemini-3.1-flash-lite`;
- `models/gemini-3.5-flash-lite`;
- `gpt-5.4-nano-2026-03-17`;
- `claude-haiku-4-5-20251001`.

Production admissions:

| Workload | Production allowlist |
|---|---|
| `gate2_source` | empty |
| `gate2_domain` | empty |
| `gate2_financial_evidence` | empty |
| `gate2_financial_checksum` | empty |

Ни synthetic status, ни общий model status не является production
admission authority.

## Current stage Function boundary

Все три Functions active. Release metadata каждой Function указывает:

- source revision:
  `efee1fede8d4e1f70ff1c54ceb7ba6dfa11584f0`;
- manifest:
  `09734d10f47760bf9f6519edbaaedc20e3ef0d29763dda71bfa6efade761d006`.

Фактическое состояние:

| Function | Live content SHA-256 | Metadata bundle SHA-256 | Accepted content origin | Repository v1.4 SHA-256 | Parity |
|---|---|---|---|---|---|
| `broker_reports_gate1_pipe` | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` | same | tree `efee1fe` | `8fbcfbc970641e5076745342c6b90da5b711bf1b0bc9c3fbcba2e3fe99fc6d94` | no |
| `broker_reports_gate2_source_fact_pipe` | `d3ba38ed554d87e01a97d7dceaffee71eaa02c88375706477d819f4ccc83d503` | same | tree `efee1fe` | `2b7a34b92700d29b0ed5e93de7fd65d9229291cd952adaf3bc84df63707db56a` | no |
| `broker_reports_gate2_domain_source_fact_pipe` | `4f5424f269e88f6e18064565afa70e11e7380033a1b6c9affc349f760a3bb0d5` | `ea5d00a513542d82689c1434396e82ce4c21222fefd217292061fa78f46505e0` | commit `b3f381b62cc79006d73268e59dc10c450b1152e7` | `4e68f73e8eba260585802edc13d65941079bf83eff7e35cfde36dbceaa3ab17e` | no |

Классификация:

- repository/live v1.4 parity: `NOT_EXACT`;
- stage release identity: `COMPOSITE`;
- domain release metadata/content parity: `NOT_EXACT`;
- Gate 1/source metadata/content parity: `EXACT_FOR_EFEE_TREE`;
- старый manifest не используется как current whole-stage receipt.

Текущие safe domain valves:

- `financial_evidence_enabled=true`;
- registry:
  `broker_reports_gate2_financial_evidence_registry_v1`;
- `max_repair_attempts=1`.

Goal 0 не изменял valves. Qualification и будущий production target требуют
repair `0`, но это отдельные последующие Goals.

## Managed prompts

Live/repository parity: `12/12`.

| Prompt | SHA-256 |
|---|---|
| `broker_reports_document_metadata_passport_prompt_v0` | `1f9827ad62e1f20c5187f92aa3814f2c149f28148a61356b52850afc301f2de6` |
| `broker_reports_gate1_clarification_prompt_v0` | `7fd0b6dc935395bfb61aeabd24194941ed32b590ba58af03ff1581849dc2048a` |
| `broker_reports_gate2_cash_movement_prompt_v0` | `c9394d07189cd3aec476a27a2fd2f3cc4b3e7883e3abaa6d43066902060d7e0e` |
| `broker_reports_gate2_currency_fx_prompt_v0` | `917c1cae378223bdd2316dc8ec7d317352107943dd5988360e7572719e1bb715` |
| `broker_reports_gate2_document_summary_evidence_prompt_v0` | `9bad1a06bb8556e0fa62f1f47de73c7d7b1d41e57aa752de9206c0749133088d` |
| `broker_reports_gate2_fee_commission_prompt_v0` | `1d7b5c5e25f1e520d55ef8e9c84d323e6a27d73da392b428a74e95a0af6910fc` |
| `broker_reports_gate2_income_prompt_v0` | `af7fcd78f4533d0f5a1f8bcef58ad113f72f102e58f547f0c30f8810ddced187` |
| `broker_reports_gate2_position_snapshot_prompt_v0` | `b250663fc078782b28dfb530f10e99ee13f97789a12d4e67852938b3088c36fd` |
| `broker_reports_gate2_source_fact_prompt_v0` | `97d7f27850e74f8869cedc2c4f8675f44933460fec3d077b192ed222230aae12` |
| `broker_reports_gate2_trade_operation_prompt_v0` | `e819ded91b58bea3012e9bd9cde0444b63427d60120ef6712e33a4d8b515c0d1` |
| `broker_reports_gate2_unknown_source_row_prompt_v0` | `776a7574542cba7b77b2c5e7686af5990c652420823bbea9a78749ac12428aa1` |
| `broker_reports_gate2_withholding_tax_prompt_v0` | `e952e09ab395d21093102e9264effd0d8fce54e5b913b57c046538168d3eb228` |

## Provider route and model inventory

Repository provider-profile revisions:

| Profile | Revision SHA-256 |
|---|---|
| `openai_gpt` | `4232f7b089fec08326548bf4c70bb33fef0ce603c23d78d6110a9c9a8aec5929` |
| `google_gemini` | `997bc0306756ddc127bf7d87b2a8e495af88f6fe03814414d1bf289eacdeeeba` |
| `anthropic_claude` | `289bf0618825d53f49ebe2fda1272aa284e5c5b23f072a262f990c80111d74e7` |

Stage `/api/models`: `41` models. Все четыре target exact IDs опубликованы:

| Exact model | Route | Active publication |
|---|---:|---|
| `gpt-5.4-nano-2026-03-17` | `urlIdx=0` | yes |
| `claude-haiku-4-5-20251001` | `urlIdx=1` | yes |
| `models/gemini-3.1-flash-lite` | `urlIdx=3` | yes |
| `models/gemini-3.5-flash-lite` | `urlIdx=3` | published aggregate entry |

Эти route identities являются publication/preflight evidence, а не
workload qualification.

Legacy live provider profiles всё ещё содержат дорогие general/visual IDs.
Они не являются economy production admissions. Goal 1 должен использовать
qualification-only boundary и не менять Gate 1 visual behavior.

## Receipt validity boundary

Следующие claims старых receipts не используются как current:

- whole-stage match старому atomic manifest;
- synthetic qualification после policy 1.4 change;
- source result как domain/financial qualification;
- stage content hash как repository v1.4 hash.

Новые workload receipts потребуются после exact qualification-only live
delivery с привязкой к policy, prompt, schema, adapter, validator и provider
route revisions.

## Verification and terminal reporting

- contracts changed: `0`;
- contracts explicitly unchanged: Registry, four-disposition, materializer,
  context projection, checksum comparator, canonical validators;
- provider calls: `0`;
- customer calls: `0`;
- token/cost: `0 / $0`;
- fallback: `0`;
- repair: `0`;
- focused tests: `136 passed`;
- full tests: `1360 passed, 20 skipped`;
- privacy: `PASSED`, customer/provider raw content not persisted;
- stage mutations: `0`;
- read-only parity verifier: expected `failed` only on three repository/live
  bundle comparisons; prompts and factory boundary passed;
- next permitted Goal: v4 Goal 1, qualification-only policy delivery with
  exact scope, rollback, and no Gate 1 visual delta.
