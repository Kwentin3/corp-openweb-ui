# Broker Reports — Gate 2 deterministic scope refactoring, Goal 3

Дата: 2026-07-25  
Статус: `GOAL_3_FINANCIAL_DECISION_INTEGRATION: PASSED`

## Результат

Реализован
`Gate2FinancialEvidenceSuccessorRunnerFactory`. Runner принимает ровно один
deterministic scope Goal 1 и выполняет один существующий Financial Evidence
decision:

`broker_reports_gate2_financial_evidence_decision_v1`.

Validated decision без нового translation/secretary contract передаётся
непосредственно в существующий
`Gate2FinancialEvidenceMaterializerFactory`.

Новый bounded model-input projection:
`broker_reports_gate2_financial_evidence_successor_model_input_v1`.

Новый prompt identity:
`broker_reports_gate2_financial_evidence_successor_prompt_v1`.

## Model input boundary

Модель получает только два top-level раздела:

- `eligible_types`;
- `source_values`.

Для каждого eligible Registry type передаются только:

- canonical `input_type_id`;
- definition;
- required/optional roles;
- role value type/cardinality;
- date/period и currency/unit requirements.

Для каждого package value передаются только:

- package-bound `source_value_ref`;
- value type;
- authoritative literal;
- allowed roles.

Model input не содержит:

- source scope/package/document/normalization IDs;
- source row/cell ref;
- source family;
- candidate/relation graph;
- fact paths;
- ownership;
- completeness/confidence/uncertainty;
- provenance/lineage/evidence;
- restrictions/issues;
- audit;
- integrity/system hashes.

Validator проверяет exact projection Registry/source package authority и
fail-closed отклоняет любой запрещённый field.

## Model output boundary

Runner передаёт provider-у существующий strict response format из
`Gate2FinancialEvidenceDecisionContract`:

- ровно четыре dispositions;
- только eligible Registry type IDs;
- только compatible role → package source-value-ref bindings;
- bounded reason codes;
- `additionalProperties: false`;
- free JSON, repair и fallback запрещены.

Никакого нового secretary decision schema не создано.

## Execution proof

Synthetic non-customer runner proof:

- Financial Evidence client calls: 1;
- source model calls: 0;
- domain model calls: 0;
- fallback: 0;
- repair: 0;
- requested/resolved synthetic execution identity:
  `gpt-5.4-nano-2026-03-17`;
- provider profile: `openai_gpt`;
- response format: `json_schema`;
- schema mode: `strict_json_schema`;
- Registry eligible types: 2;
- package values: 6;
- terminal disposition:
  `unclassified_financial_input`;
- existing materializer reused.

Hashes:

- existing decision schema:
  `09914317fb64eb280c3b5db86b63f37eb0ff615eda29a4b7a1b54b031e502f31`;
- Registry:
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`;
- successor prompt:
  `83f22755dd8380b4d91a5b143b1c991afdbed25afea959d9be3d882faee7f33b`;
- model input:
  `66721bd82413736a54a2b3f8adc36d7a6e0dc92b6f544bbf16c40b6bb849bb99`;
- materialized artifact:
  `765384adad22cd976528fc5f915e0f880193af1fa5f3ba3d1ecf48daa5b1445f`.

Это local synthetic contract proof с fake client, а не live provider
qualification.

## Closed-world bundle proof

Domain bundle dependency closure теперь содержит:

1. existing financial Registry/decision/materializer modules;
2. existing domain router/packages/segmenter;
3. `gate2_deterministic_financial_scopes`;
4. `gate2_financial_evidence_successor`.

Порядок загрузки проверяется тестом. Повторная сборка bundle exact
детерминирована.

Repository domain bundle SHA-256:
`2a8d9ec8c643510b7f4974d77208c1f4fba5f232bd1b07c6d1960bf984634abe`.

Main domain pipe пока не вызывает successor runner: его customer-facing
route и stage не переключались. Bundle availability не является production
activation.

## Negative proof

Fail-closed тесты покрывают:

- fallback;
- repair;
- missing execution metadata;
- wrong exact model/profile/structured-output metadata;
- `json_object` вместо strict schema;
- out-of-package model ref;
- model-authored audit/system field;
- model-input lineage/system-field injection;
- source/domain/legacy production runtime imports в successor module.

## Tests

- direct Goal 3:
  `10 passed in 0.63s`;
- focused successor/scope/decision/materialization/bundle:
  `75 passed in 2.81s`;
- full Broker Reports suite:
  `1427 passed, 20 skipped, 5 warnings in 92.66s`;
- Ruff:
  `All checks passed`;
- `git diff --check`:
  passed;
- bundle rebuild exact:
  true.

## Repository and Git boundary

- base revision:
  `5759da886b9ff512050be30ff9ca11e32b46c3e4`;
- branch:
  `codex/broker-reports-gate2-scope-refactor-goal3-financial-integration`;
- implementation revision:
  `ecaddabcb2e810884fecde7f15455a87f04c8ec0`;
- PR: `PENDING`;
- stage mutations: 0;
- customer-facing routing changes: 0;
- legacy runtime deletion: 0.

Successor source SHA-256:
`2c5c645d9156f6b94ebfecd083b9745c415747dd242abede635f1cc32095db39`.

Test source SHA-256:
`7114cf20753aceb41c6890b41e73e457ad32ad616855c183fa7bd02d77f4b962`.

## Privacy and external effects

- live provider calls: 0;
- customer corpus calls: 0;
- persistence writes: 0;
- browser/stage calls: 0;
- stage mutations: 0;
- raw model output in Git: 0;
- customer/private values, refs or paths in Git evidence: 0.

## Acceptance

- `NEW_SEMANTIC_AUTHORITY: ZERO`
- `MODEL_SYSTEM_FIELDS: ZERO`
- `PACKAGE_BOUND_REFS: ONLY`
- `REGISTRY_BOUND_IDS: ONLY`
- `EXISTING_MATERIALIZER: REUSED`
- `SOURCE_DOMAIN_MODEL_CALLS: ZERO_IN_SUCCESSOR_PATH`

## Next permitted Goal

Только после merge этого отдельного PR разрешён Goal 4: bounded
actual-corpus qualification successor path. Goal 3 сам по себе не является
actual-corpus proof, production admission или stage release.
