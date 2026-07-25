# Broker Reports — Gate 2 Economy v3, Goal 1: workload-specific policy

Дата: 2026-07-25

Статус: `PASSED_FOR_POLICY_DELIVERY`

Production activation: `NOT_PERFORMED`

## Итог

Доставлен successor economy policy `1.4.0` и отдельный workload policy
`1.4.0`. Общий статус модели больше не является authority для production
admission. Единственная разрешённая граница выбора — exact model ID и
квалификация для конкретного workload.

Acceptance:

- `WORKLOAD_POLICY: VERSIONED`;
- `GENERAL_MODEL_QUALIFICATION: NOT_USED`;
- `PRODUCTION_ALLOWLIST: EMPTY`;
- `EXPENSIVE_IDS: ABSENT` в economy v3 workload contour;
- `STAGE_MUTATIONS: ZERO`.

Gate 1 visual model policy не менялся: это явный non-goal программы.

## Authorities

| Authority | Identity | SHA-256 |
|---|---|---|
| Model policy | `broker_reports_economy_model_policy_v1`, `1.4.0`, schema `broker_reports_economy_model_policy_v2` | `e71bbb7c95774058bc2324343a2de2adef2f3307d8b30f8e92d8cbf514bd09c9` |
| Workload policy | `broker_reports_gate2_economy_workload_policy_v2`, `1.4.0` | `f1eb7daa08f10c125d21addb5ec03a5dfac42207cc39a4b3aa86224820fc3a7d` |
| Qualification registry | schema `broker_reports_gate2_economy_workload_qualification_v2`, 16 current subjects | `9a5923d61bf8ca73db2ce6acc37e9c2ea85d2c197625f15469b6cac5dae54c23` |

Model policy содержит только четыре exact ID:

- `models/gemini-3.1-flash-lite`;
- `models/gemini-3.5-flash-lite`;
- `gpt-5.4-nano-2026-03-17`;
- `claude-haiku-4-5-20251001`.

Aliases, `latest`, preview/moving IDs и все дорогие модели не входят в v3
policy. Runtime config может только сузить уже существующие workload
production admissions. Сейчас admissions отсутствуют, поэтому любой
runtime override fail-closed отклоняется до provider invocation.

## Target workload matrix

| Workload | Primary candidate | Secondary candidate | Diagnostic candidate | Max fallback | Production |
|---|---|---|---|---:|---|
| `gate2_source` | Gemini 3.1 Flash-Lite | Gemini 3.5 Flash-Lite | — | 1 economy candidate | empty |
| `gate2_domain` | Gemini 3.1 Flash-Lite | Gemini 3.5 Flash-Lite | — | 1 economy candidate | empty |
| `gate2_financial_evidence` | GPT-5.4 Nano | Gemini 3.5 Flash-Lite | Gemini 3.1 Flash-Lite | 1 economy candidate | empty |
| `gate2_financial_checksum` | Claude Haiku 4.5 | GPT-5.4 Nano | Gemini 3.1/3.5 Flash-Lite | 0 | empty |

Reasoning controls остаются model-specific:

- GPT-5.4 Nano: `disabled`;
- Gemini 3.1/3.5: `minimal`;
- Claude Haiku 4.5: `disabled`, без extended thinking;
- paid tools: запрещены для всех четырёх моделей.

## Qualification identity

Каждая запись реестра связывает:

`exact model ID × provider profile × provider route revision × workload ×
input contract × output contract × prompt × adapter projection × canonical
validator`.

Текущие contract identities:

| Workload | Input | Output | Prompt | Canonical validator |
|---|---|---|---|---|
| source | `broker_reports_gate2_source_fact_package_v0` | `broker_reports_source_facts_v0` | `broker_reports_gate2_source_fact_prompt_v0` | `source_fact_canonical_validator_v0` |
| domain | `broker_reports_domain_extraction_package_v0` | `broker_reports_candidate_binding_output_v0+broker_reports_domain_source_facts_v0` | `broker_reports_gate2_domain_prompt_v0` | `domain_source_fact_canonical_validator_v0` |
| financial evidence | `broker_reports_gate2_financial_evidence_source_package_v1` | `broker_reports_gate2_financial_evidence_decision_v1` | `gate2_financial_evidence_shadow_prompt_v1` | `sha256:747d83552f394f4bd56249820e9630adc97a4d2435da60cbd9b2b376685eb5be` |
| checksum | `broker_reports_gate2_financial_context_v1` | `broker_reports_gate2_financial_context_checksum_v1` | `gate2_financial_context_checksum_prompt_v1` | `sha256:561caa46ca51fc538a849df7eff6e2a97419c1e3fb700c7e90d055a258b0bcb9` |

Adapter projections:

- OpenAI: `gate2_openai_response_format_adapter_v1`;
- Gemini: `gate2_gemini_schema_projection_v1`;
- Anthropic: `gate2_anthropic_structural_projection_v1`.

## Current workload subjects

Goal 1 не выполнял новые provider calls. Synthetic status ниже перенесён
только как revision-bound evidence state из
`BROKER_REPORTS_ECONOMY_REQUALIFICATION_V2`; он не активирует production.
Actual-corpus, full-scope use count, новые token/cost measurements для всех
subjects: `NOT_RUN_IN_GOAL1`.

| Exact model | Provider | Workload | Route revision | Synthetic status | Calls | Fallback | Repair | Qualification |
|---|---|---|---|---|---:|---:|---:|---|
| Haiku 4.5 | `anthropic_claude` | domain | `not_applicable` | not selected | 0 | 0 | 0 | `not_in_target_matrix` |
| Haiku 4.5 | `anthropic_claude` | checksum | `openwebui_0.9.6_maintained_route_2026-07-24` | `3/3` | 1 | 0 | 0 | `synthetic_qualified` |
| Haiku 4.5 | `anthropic_claude` | financial evidence | same maintained route | `2/4`; typed schema reject and unsupported mismatch | 4 | 0 | 0 | `not_qualified` |
| Haiku 4.5 | `anthropic_claude` | source | `not_applicable` | not selected | 0 | 0 | 0 | `not_in_target_matrix` |
| GPT-5.4 Nano | `openai_gpt` | domain | `not_applicable` | not selected | 0 | 0 | 0 | `not_in_target_matrix` |
| GPT-5.4 Nano | `openai_gpt` | checksum | `openwebui_0.9.6_maintained_route_2026-07-24` | `0/3`, dimension mismatch | 1 | 0 | 0 | `not_qualified` |
| GPT-5.4 Nano | `openai_gpt` | financial evidence | same maintained route | `4/4` | 4 | 0 | 0 | `synthetic_qualified` |
| GPT-5.4 Nano | `openai_gpt` | source | `not_applicable` | not selected | 0 | 0 | 0 | `not_in_target_matrix` |
| Gemini 3.1 | `google_gemini` | domain | `pending_stage_delivery_policy_1_4` | exact replay required | 0 | 0 | 0 | `pending_stage_delivery` |
| Gemini 3.1 | `google_gemini` | checksum | `maintained_route_not_exercised_policy_1_4` | optional later | 0 | 0 | 0 | `diagnostic_not_scheduled` |
| Gemini 3.1 | `google_gemini` | financial evidence | `openwebui_0.9.6_maintained_route_2026-07-24` | unclassified shape invalid | 1 | 0 | 0 | `not_qualified` |
| Gemini 3.1 | `google_gemini` | source | `pending_stage_delivery_policy_1_4` | exact replay required | 0 | 0 | 0 | `pending_stage_delivery` |
| Gemini 3.5 | `google_gemini` | domain | `pending_stage_delivery_policy_1_4` | exact replay required | 0 | 0 | 0 | `pending_stage_delivery` |
| Gemini 3.5 | `google_gemini` | checksum | `maintained_route_not_exercised_policy_1_4` | optional later | 0 | 0 | 0 | `diagnostic_not_scheduled` |
| Gemini 3.5 | `google_gemini` | financial evidence | `pending_stage_delivery_policy_1_4` | route delivery required | 0 | 0 | 0 | `pending_stage_delivery` |
| Gemini 3.5 | `google_gemini` | source | `pending_stage_delivery_policy_1_4` | exact replay required | 0 | 0 | 0 | `pending_stage_delivery` |

Из старого synthetic evidence сохранены только aggregate token/cost данные:
GPT successful cost `$0.002279900`; Haiku financial/checksum successful cost
`$0.012437`. Они не разнесены по всем 16 subjects и не используются как
production budget authority.

## Runtime and anti-drift boundary

- model-level `qualified` status запрещён как admission authority;
- production admission требует workload-specific qualification receipt,
  actual-corpus receipt и full-scope receipt, каждый как SHA-256;
- selection factory связывает model policy и workload policy по exact
  version/hash;
- qualification accepts только exact candidate IDs;
- budget finalization отклоняет provider-resolved alias;
- provider selection сохраняет code-owned primary/secondary order;
- fallback не повышает tier и ограничен одним economy candidate; checksum
  fallback равен нулю;
- общий runtime config не может расширить allowlist;
- generated bundles включают workload policy через canonical bundle builder.

## Verification

- focused workload/policy/budget/checksum/bundle/live-contract suite:
  `87 passed`;
- migration boundary regression: `12 passed`;
- full service suite: `1360 passed, 20 skipped`;
- Ruff по изменённому Goal 1 scope: passed;
- `compileall` для package, actions и scripts: passed;
- три последовательных bundle build: byte-stable;
- provider/customer calls в Goal 1: `0`;
- stage writes в Goal 1: `0`.

Bundle SHA-256:

- Gate 1:
  `8fbcfbc970641e5076745342c6b90da5b711bf1b0bc9c3fbcba2e3fe99fc6d94`;
- Gate 2 source:
  `2b7a34b92700d29b0ed5e93de7fd65d9229291cd952adaf3bc84df63707db56a`;
- Gate 2 domain:
  `4e68f73e8eba260585802edc13d65941079bf83eff7e35cfde36dbceaa3ab17e`.

Полный Ruff по историческому `broker_reports_gate1/__init__.py` имеет 64
pre-existing F401 и в baseline Goal 0, и в текущем tree; Goal 1 не расширяет
этот known baseline. Изменённые модули и тесты проходят Ruff.

## Release gate

Эта поставка пригодна для отдельного merge/review policy route. Она не
квалифицирует Gemini заново, не переносит synthetic evidence в production и
не меняет stage. Goal 2 может начаться только после merge/принятия и доставки
этого exact policy route на stage.
