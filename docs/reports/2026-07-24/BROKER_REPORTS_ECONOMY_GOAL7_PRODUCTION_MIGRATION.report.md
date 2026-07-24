# Broker Reports — Economy Goal 7: controlled production migration

Дата: 2026-07-24

Терминальный статус: `NOT_CLOSED`.

## Release decision

Economy policy не выпущена в stage. Обязательные release preconditions не
выполнены:

- qualified economy models: `0`;
- Goal 5 full-scope economy reproof: `NOT_CLOSED`;
- Goal 6 economy checksum: `NOT_CLOSED`.

Атомарный release, bounded persistence verifier и rollback exercise не
запускались. Functions, prompts и valves не изменялись.

## Migration verifier guard

Опасный default `gpt-5.6-sol` удалён из controlled migration verifier.
Verifier теперь до authentication, scope read и chat completion выполняет
economy selection для `gate2_financial_evidence`.

Текущий terminal preflight:

`gate2_economy_no_qualified_model`.

Явный `gpt-5.6-sol` отклоняется как
`economy_model_not_registered`. Migration body фиксирует
`max_repair_attempts = 0`.

Для обоих blockers:

- provider calls: `0`;
- fallback calls: `0`;
- expensive model calls: `0`;
- stage mutations: `0`.

## Read-only live state

Выполнены только authenticated GET/read-only snapshots.

| Function | Live SHA-256 | Repository candidate SHA-256 | Parity |
| --- | --- | --- | --- |
| `broker_reports_gate1_pipe` | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` | `0b57d294e135bdbdfd0e8fa374218ef12a08dc3f415a50482b2b7aee2681738d` | no |
| `broker_reports_gate2_source_fact_pipe` | `d3ba38ed554d87e01a97d7dceaffee71eaa02c88375706477d819f4ccc83d503` | `d1c329fade86d9cf8cc6f26977e0bc017ccef743f082e6d506ac52ed66f8e5c9` | no |
| `broker_reports_gate2_domain_source_fact_pipe` | `4f5424f269e88f6e18064565afa70e11e7380033a1b6c9affc349f760a3bb0d5` | `947cd4217d13b75fe1af35cfbf349db8cb52c5a2491e39792340ff660c3895fb` | no |

Live Gate 2 Functions не содержат
`Gate2EconomyProviderSelectionFactory` и не включают
`economy_budget_enforcement=True`; старый resolver marker присутствует.
Следовательно, `ECONOMY_POLICY_LIVE` не является exact.

Safe domain valves:

- `financial_evidence_enabled`: `true`;
- Registry version:
  `broker_reports_gate2_financial_evidence_registry_v1`;
- `model_id` / `provider_profile_id`: отсутствуют;
- `max_repair_attempts`: `1` — candidate economy release должен был бы
  изменить это значение, но release запрещён preconditions.

Ни один из этих read-only checks не выполнял chat completion.

## Persistence и rollback

- new economy financial run: `NOT_RUN`;
- new receipt/context/input artifacts: `0`;
- exact economy model persisted: `NO`;
- cost evidence persisted: `NO`;
- Knowledge/RAG/vector delta: `0` по отсутствию write operation;
- current-candidate rollback: `NOT_RUN_NO_RELEASE`.

Предыдущая rollback identity другого принятого release не считается
rollback proof для невыпущенного economy candidate.

## Provider blocker

Owning boundary: maintained provider connections/adapters и qualification
harness.

- OpenAI Nano: exact IDs отсутствуют, terminal
  `stage_models_endpoint_model_absent`; запрещены Mini/Sol/full GPT/o-series.
- Gemini 3.1 Flash-Lite: canonical reject
  `financial_evidence_decision_unclassified_shape_invalid`; запрещены Flash и
  Pro.
- Gemini 3.5 Flash-Lite: financial qualification route отсутствует,
  `financial_qualification_not_exposed_by_capability_probe_route`; запрещены
  Flash и Pro.
- Haiku 4.5: schema reject
  `gate2_model_schema_response_format_rejected`; запрещены Sonnet и Opus.

Узкий следующий шаг: закрыть один provider contract, принять qualification,
затем последовательно повторить Goals 5 и 6. Только после этого формировать
candidate release manifest и bounded persistence proof.

## Проверки

- migration guard + selection + checksum focused suite: `22 passed`;
- full regression suite: `1332 passed, 20 skipped`;
- read-only stage snapshots: `passed`;
- live provider calls: `0`;
- stage mutations: `0`.

## Acceptance

- `ECONOMY_POLICY_LIVE`: `NOT_RELEASED`;
- `BOUNDED_PERSISTENCE`: `NOT_RUN`;
- `EXPENSIVE_MODEL_LIVE_CALLS`: `ZERO`;
- `ROLLBACK`: `NOT_RUN_NO_RELEASE`;
- `GOAL_7_PRODUCTION_MIGRATION`: `NOT_CLOSED`.
