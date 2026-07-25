# Broker Reports — Economy v3 Goal 0: current authorities

Дата проверки: 2026-07-25.

Статус: `PASSED_WITH_EXPLICIT_REPOSITORY_STAGE_REVISION_BOUNDARY`.

## Результат

Текущие repository и stage authorities закреплены раздельно. Stage не
изменился после принятого receipt от 2026-07-24, но candidate repository
содержит policy/qualification изменения, которые ещё не выпускались.
Поэтому старый stage hash не используется как hash текущего repository, а
synthetic qualification не переносится на иной contract/policy revision.

Stage mutations в Goal 0: `0`.

## Repository authority

- branch: `codex/broker-reports-economy-requalification-v2`;
- revision: `2d6d428`;
- base `origin/main`: `d6c4649`;
- economy policy: `1.3.0`;
- economy policy hash:
  `ce1a2842fe61e325fefdc0adb5a6a78729b8e7cab24988e4059636b3f215ffc3`;
- workload qualification registry:
  `broker_reports_gate2_economy_workload_qualification_v1`;
- workload registry hash:
  `72392d9d707c7d21e2975f60fb033e1aebecdb6a29e109e227a1d48ccfde55d7`;
- Financial Evidence Registry:
  `broker_reports_gate2_financial_evidence_registry_v1`;
- Financial Evidence Registry hash:
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`;
- production allowlists: пусты для всех четырёх workloads.

### Authority file SHA-256

| Authority | SHA-256 |
| --- | --- |
| Financial Evidence Registry | `0c2bfdea806c423b5a20402a54a9150ece90f5d93e759edc1b67f8ff0ea13efe` |
| four-disposition decision contract | `747d83552f394f4bd56249820e9630adc97a4d2435da60cbd9b2b376685eb5be` |
| deterministic materialization | `543633b6e133d761f669450402647af80703ab000a3ba5e5132a0888be8eb434` |
| financial context projection | `9516f9b3d1dc7171cc85346c79aba46e999a4f33c8b76efb35b808d8df78b7a3` |
| financial checksum contract/comparator | `561caa46ca51fc538a849df7eff6e2a97419c1e3fb700c7e90d055a258b0bcb9` |
| economy policy v1.3 | `1ee085d91f64d17744b8ecbd5896ffc58f67203e5e9568e1c80659f0e21e7fd2` |
| workload qualification registry | `e8619c149d9e55fb640240b13a3d17749384a1553d8e6b3a7c4c54cb2427c087` |

## Live stage authority

- OpenWebUI models: `41`;
- все четыре разрешённые v3 exact model IDs опубликованы;
- managed prompts: `12/12`, repository/live content parity passed;
- stage release source revision:
  `efee1fede8d4e1f70ff1c54ceb7ba6dfa11584f0`;
- stage release manifest:
  `09734d10f47760bf9f6519edbaaedc20e3ef0d29763dda71bfa6efade761d006`.

| Function | Active | Live SHA-256 | Candidate repository SHA-256 | Parity |
| --- | --- | --- | --- | --- |
| `broker_reports_gate1_pipe` | yes | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` | `0b57d294e135bdbdfd0e8fa374218ef12a08dc3f415a50482b2b7aee2681738d` | no |
| `broker_reports_gate2_source_fact_pipe` | yes | `d3ba38ed554d87e01a97d7dceaffee71eaa02c88375706477d819f4ccc83d503` | `d1c329fade86d9cf8cc6f26977e0bc017ccef743f082e6d506ac52ed66f8e5c9` | no |
| `broker_reports_gate2_domain_source_fact_pipe` | yes | `4f5424f269e88f6e18064565afa70e11e7380033a1b6c9affc349f760a3bb0d5` | `947cd4217d13b75fe1af35cfbf349db8cb52c5a2491e39792340ff660c3895fb` | no |

Stage bundle hashes и release identity совпадают с принятым Goal 9 receipt
от 2026-07-24. Несовпадение относится к ещё не выпущенному candidate
repository и не является самовольной stage mutation.

Текущий domain valve `max_repair_attempts=1`. В v3 production target должен
быть `0`; это отдельное будущее release изменение и не выполняется в Goal 0.

## Exact model inventory

| Exact model | Published |
| --- | --- |
| `models/gemini-3.1-flash-lite` | yes |
| `models/gemini-3.5-flash-lite` | yes |
| `gpt-5.4-nano-2026-03-17` | yes |
| `claude-haiku-4-5-20251001` | yes |

Gemini 2.5 Flash-Lite исключён из активного плана. Новые providers и
дорогие models не добавлялись.

## Receipt validity boundary

- v2 synthetic receipts сохраняются только для exact policy/contract
  revisions, на которых были получены;
- после successor policy или adapter/prompt correction требуется новый
  exact workload receipt;
- source success не переносится на domain или financial;
- synthetic status не активирует production selection;
- old live hashes не выдаются за repository/live parity.

## Acceptance

- `CURRENT_AUTHORITIES: PINNED`;
- `STALE_RECEIPTS_USED_AS_CURRENT: ZERO`;
- `STAGE_UNCHANGED_SINCE_2026_07_24_ACCEPTED_RECEIPT: YES`;
- `REPOSITORY_STAGE_REVISION_BOUNDARY: EXPLICIT`;
- `PRODUCTION_ALLOWLIST: EMPTY`;
- `STAGE_MUTATIONS: ZERO`.
