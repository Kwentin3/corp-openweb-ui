# Broker Reports — Gate 2 deterministic scope refactoring, Goal 6

Дата: 2026-07-25  
Статус: `GOAL_6_EXACT_MODEL_QUALIFICATION: NOT_QUALIFIED`

## Результат

Exact model `gpt-5.4-nano-2026-03-17` не квалифицирована для successor
Financial Evidence workload.

Обе bounded попытки на frozen 11-case synthetic corpus:

- использовали опубликованную exact model через pinned `openai_gpt` route;
- получили strict structured output;
- прошли существующий canonical decision validator во всех 22 вызовах;
- не использовали free JSON, repair, fallback или дорогую модель;
- не вызывали source/domain models;
- не читали customer corpus и не меняли production/stage.

Однако ни одна попытка не прошла frozen product expectations для всех четырёх
dispositions. Это terminal qualification failure, а не transport/schema
failure.

## Qualification identity

- exact model: `gpt-5.4-nano-2026-03-17`;
- provider profile: `openai_gpt`;
- provider route revision:
  `4232f7b089fec08326548bf4c70bb33fef0ce603c23d78d6110a9c9a8aec5929`;
- deterministic scope:
  `broker_reports_gate2_deterministic_financial_scope_package_v1`;
- Registry version:
  `broker_reports_gate2_financial_evidence_registry_v1`;
- Registry hash:
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`;
- decision contract:
  `broker_reports_gate2_financial_evidence_decision_v1`;
- frozen manifest canonical hash:
  `2ad54a8dae7e9e34a4d020310acffad5c76dc049855e5440ed557fb1efe4d687`;
- frozen manifest file SHA-256:
  `b607112e1a70f9877dbd935fdb6f6fe666b61be1ed5b290e896270bde1af886c`.

Qualification также pin-ит prompt, provider projection, canonical validator,
materializer, product comparator и fixture manifest. Model-facing successor
decision contract не создан.

## Zero-call preflight

Prompt-v2 preflight подтвердил:

- exact model опубликована;
- qualification action active и qualification-only;
- 11 strict-schema вызовов разрешены;
- maximum estimated input: 3057 из 3072 tokens;
- total estimated input: 29133 tokens;
- maximum output: 640 tokens на вызов;
- estimated maximum cost: `$0.014626600`;
- provider calls: 0.

Authorization identity:
`8dd5285c21164886e2830483eb93427eb8ae9889c38de1a5494bdd53f6ca1ff3`.

## Bounded live attempt 1

Prompt:
`broker_reports_gate2_financial_evidence_successor_prompt_v1`.

- cases passed: 7/11;
- cases failed: 4/11;
- canonical validation: 11/11;
- dispositions observed:
  `typed_input=6`,
  `unclassified_financial_input=4`,
  `no_financial_input=0`,
  `unsupported=1`;
- input/output tokens: 22315/1821;
- provider calls: 11;
- actual cost: `$0.006739250`.

Четыре failure были semantic expectation mismatches: модель неверно различила
printed metric, ordinary cash balance, repeated header и adjacent equal-value
binding. Validator, materializer и artifact family при этом оставались
fail-closed и канонически валидными.

Private checkpoint SHA-256:
`e2f68329f33e50acc3db8e149546041fcf47625074d1587f330932d685277a8f`.

## Bounded live attempt 2

Была сделана одна evidence-driven коррекция prompt contract до
`broker_reports_gate2_financial_evidence_successor_prompt_v2`. Registry,
decision schema, provider schema, validator, materializer, comparator и budget
не менялись.

- cases passed: 9/11;
- cases failed: 2/11;
- canonical validation: 11/11;
- dispositions observed:
  `typed_input=9`,
  `unclassified_financial_input=0`,
  `no_financial_input=1`,
  `unsupported=1`;
- input/output tokens: 23393/1459;
- provider calls: 11;
- actual cost: `$0.006502350`.

Пройденные в первой попытке problem classes были исправлены. Остались два
semantic expectation mismatches:

- `multiple_hypotheses`: ожидался `unclassified_financial_input`, получен
  `typed_input`;
- `explicit_unclassified`: ожидался `unclassified_financial_input`, получен
  `typed_input`.

Product comparator зафиксировал две затронутые source refs, но подтвердил:

- literal loss: 0;
- invented values: 0;
- duplicate bindings: 0;
- cross-scope bindings: 0;
- terminal ownership gaps: 0;
- production write admitted: false.

Private checkpoint SHA-256:
`5332f99a2a3b10bc6d2594fc3aee0c93ce494ba4730eeeac6a9d58303d3b8271`.

## Aggregate external accounting

Для обеих live attempts вместе:

- Financial Evidence model calls: 22;
- input tokens: 45708;
- output tokens: 3280;
- actual cost: `$0.013241600`;
- source model calls: 0;
- domain model calls: 0;
- expensive model calls: 0;
- fallback: 0;
- repair: 0;
- customer calls: 0;
- production/stage mutations: 0.

## Tests

- direct Goal 6: `20 passed in 3.74s`;
- focused successor/budget/bundle:
  `75 passed in 7.32s`;
- full Broker Reports suite:
  `1457 passed, 20 skipped, 5 warnings in 107.66s`;
- Ruff по изменённым module/script/test files: `All checks passed`;
- `git diff --check`: passed;
- repeated bundle rebuild exact: true.

Current bundle SHA-256:

- Gate 1:
  `1737afd026c51fa50c05bc2216509a15f19a6829faeed973463de9c6cb84d0d6`;
- Gate 2 source:
  `499c631f877c56f5f41a37dcc9b663556870523208fb2cb47a5bae2e3720a766`;
- Gate 2 domain:
  `ed493a04338795836a88c878acc8516bb150f63869465d6c25bdca5bea23326d`.

## Repository and Git boundary

- base revision:
  `20cf1b6af9d29a862d45e3dd8ec35c592c8c657c`;
- branch:
  `codex/broker-reports-gate2-scope-refactor-goal6-exact-model-qualification`;
- implementation revisions:
  `dc1c915fcc2c4430ad235c54a2f1541105830f58`,
  `0ebc3e9631b04d2e7020a8aef82eec7ebe9ab3bc`;
- PR: `https://github.com/Kwentin3/corp-openweb-ui/pull/132`.

Changed contracts:

- qualification-only Financial Evidence request profile;
- exact successor qualification identity/runner;
- prompt contract v1 → v2 after first bounded evidence.

Explicitly unchanged:

- Financial Evidence Registry v1;
- canonical decision contract and validator;
- deterministic materializer and product comparator;
- legacy immutable artifact policy;
- source/domain model authority remains zero;
- production admission remains false.

## Privacy

- raw provider output in Git: 0;
- customer values, refs, payloads or paths in Git evidence: 0;
- committed receipt contains only aggregate, identities and synthetic case
  classifications;
- private atomic checkpoints remain outside Git.

## Acceptance and terminal stop

- `FINANCIAL_MODEL: NOT_QUALIFIED_FOR_SUCCESSOR_WORKLOAD`
- `FOUR_DISPOSITIONS: FAILED`
- `CANONICAL_VALIDATION: PASSED`
- `FALLBACK: ZERO`
- `REPAIR: ZERO`
- `EXPENSIVE_MODEL: ZERO`

Goal 6 terminally classified. Дополнительные prompt/model/Registry итерации в
этом program не разрешены. Goals 7–14 зависят от успешной Goal 6 qualification
и потому не запускаются.
