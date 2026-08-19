# G5.20 — Independent Declaration Authoring Report

Дата: 2026-08-10

Статус: `PARTIALLY_PROVEN`

Product status: `INACTIVE PROOF`; публикации и activation нет.

## Итог

На финальный вопрос G5.20 ответ — **частично**.

Clean-context LLM реально дошла до inference, вернула один наблюдаемый
машиночитаемый JSON candidate, самостоятельно нашла поддерживаемую Appendix 8
часть и реальную границу с Section 2. Три direct-projection compilation units
точно совместимы с repository truth.

Но весь candidate не прошёл неизменённый neutral semantic validator. Поэтому
нельзя утверждать, что независимая LLM уже способна безошибочно сформировать
полный исполнимый Declaration Definition Package.

## Context bootstrap

- Домен: inactive Gate 5 Declaration Definition authoring proof.
- Sole owner: `Gate5CleanContextDeclarationTrialFactory.create`.
- Inputs: official G5.16 evidence, G5.18 capability v1/behavior registry,
  G5.8 methodology authority и G5.12 projection owner.
- Compatibility: G5.19 strict-schema attempts и payload bytes сохранены.
- Изменён только outer authoring transport/parser boundary.
- Application provider path, case-time runtime и tax semantics не менялись.
- Второй runtime/capability/artifact authority не создан.

## Как технический contour был доведён до inference

Provider strict schema удалён из invocation, но closed Draft 2020-12 schema
остался частью exact model-visible payload и применялся локально после capture.
Новый parser принимает ровно один UTF-8 JSON object и fail-closed отвергает:

```text
empty response;
Markdown fence;
два JSON objects;
не-object JSON root.
```

Перед semantic trial выполнен отдельный non-semantic canary. Он не видел
declaration evidence, capabilities или artifacts и с первого inference вернул
exact 68-byte JSON object. Repair/retry — 0.

Официальная документация OpenAI подтверждает, что
`--output-last-message` сохраняет final assistant message для downstream
scripting, а `--output-schema` является отдельной опцией. Structured Outputs
принимает только subset JSON Schema и отклоняет неподдерживаемую strict schema.
Проверено 2026-08-10:
[Codex developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli),
[Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## Blind input

Semantic input не менялся по ответу модели. Использован exact G5.19 v1 payload:

```text
bytes   27013
sha256  a3ad620016c93eff08a7f79cdb24f86cdcc81b0dd16ce7a68be2660d760fac46
history none
bias audit passed
```

Модель получила только шесть разрешённых sections: system instructions,
research policy, Runtime Capability Contract v1, published inventory, official
evidence и neutral output schema. Expected gap, G5 history, предыдущий candidate
и roadmap отсутствовали. Единственный `line 060` находился внутри official
evidence.

## Inference и capture

### Attempt 001

Первый semantic submission дошёл до inference, но outer experiment передал
испорченный Cyrillic absolute output path. Provider process вернул `0`, однако
readable final-message file не появился.

Ответ не наблюдался, не хешировался, не парсился и не мог участвовать в выборе.
Это честно сохранённый harness failure, а не model verdict.

### Attempt 002

Второй attempt изменил только capture route на уже доказанный canary temp-path
pattern. Exact semantic payload остался byte-identical.

```text
response bytes   20848
response sha256  093879f7e08cbba68ce0ab0df938acf86b8a0a0708cf8c04f0a6818848d15a75
JSON parse       passed
JSON Schema      passed
model follow-up  0
manual repair    0
```

Это единственный наблюдаемый candidate, поэтому выбирать лучший ответ было не
из чего. Capture recovery и два completed semantic inferences остаются явным
ограничением proof.

## Что LLM поняла правильно

Candidate содержит 10 requirements и 5 gaps. Модель правильно нашла три
conditionally compilable Appendix 8 units и привязала их к существующей
capability/artifact паре:

```text
appendix8_five_operation_semantics
appendix8_operation_code_01
appendix8_electronic_occurrence

project_validated_declaration_fragment_v0
ru-3ndfl-2025-appendix8-securities-proof@2026.0-proof
```

У этих units exact input/output contracts, evidence refs и artifact identity
прошли ordinary-code repository validation.

Модель также нашла существующие identities:

```text
execute_published_typed_behavior_v1
securities_disposal_operation_tax_model_v0
aggregate_complete_category_scope_v0
ru-ndfl-securities-tax-model-proof@2026.1-experimental
```

То есть composition direction была понята, хотя один wrapper binding оказался
неточным.

## Первый настоящий blocker

Модель указала:

```text
appendix8_expense_to_section2_gap
type = incompatible_contract
```

Смысл gap: текущий published projection заканчивается Appendix 8 fragment и не
связывает accepted line 040 expense с group-bound Section 2 calculation.

Repository truth подтверждает это отсутствие. Также действительно отсутствуют
published Section 2 projection artifact и registered Section 2 calculation
behavior. Это реальная более ранняя граница dependency chain, а не требование
совпасть с историческим ожидаемым названием gap.

Blocker модели не подсказывался: его ID, Appendix 8-to-Section 2 формулировка и
expected classification отсутствуют вне official evidence.

## Что не прошло deterministic validation

Closed JSON Schema, target identity и authoring flags прошли. Unchanged neutral
validator остановился на первом semantic нарушении:

```text
gate5_clean_context_candidate_case_evidence_overclaim
field = requirements[0]
```

Полный non-mutating repository audit выявил три defects:

1. `target_order_and_period` объявлен `compilable` и end-to-end available без
   capability binding;
2. в `appendix8_repeated_occurrences` correct registered behavior привязан к
   semantic input contract вместо exact wrapper inputs
   `behavior_ref + contract identities + registered_behavior_input + context`;
3. gap `section2_calculation_behavior_gap` классифицирован как
   `missing_published_behavior`, но обязательный `missing_behavior_id` оставлен
   null.

Итог ordinary-code audit:

```text
requirements              10: 8 passed, 2 failed
capability bindings        6:  5 passed, 1 failed
gap taxonomy objects       5:  4 passed, 1 failed
valid supported units      3
candidate mutations        0
manual repairs             0
```

Ошибки модели сохранены как результат эксперимента. Candidate не исправлялся и
не превращался в authority.

## Почему verdict PARTIALLY_PROVEN

Условия частичного доказательства выполнены:

- real inference и machine-readable output получены;
- clean context и official-evidence boundary сохранены;
- модель не придумала capability, artifact, formula, case value или tax rule;
- поддерживаемая direct projection часть определена корректно;
- реальный unsupported Section 2 boundary найден без подсказки;
- exact compilation package не получился из-за локализованных authoring-contract
  ошибок.

Это не `PROVEN`, потому что candidate целиком не компилируется. Это не
`NOT_PROVEN`, потому что три полезных composition units и основной system
boundary корректны.

## KISS и архитектурная граница

G5.20 добавил только:

- additive plan/parser methods у существующего owner;
- plain final-message capture вместо provider strict schema;
- focused parser tests;
- immutable candidate и safe evidence;
- v1 contract, authority update и этот report.

Не добавлены capability, behavior, methodology, Tax Model, input kind,
Reference Data, workflow DSL, runner, DB, GUI, XML/PDF или activation.

`architecture-blueprint-guardrails` сохранил authoring output как proposal на
границе: runtime исполняет только published deterministic owners. Навык
`pb-tests-integrity` не позволил сделать candidate green через repair или
snapshot expectation; terminal outcome — реальный validator failure.

## Validation

PowerShell, explicit `PYTHONPATH`, реальные terminal outcomes:

- focused G5.20/G5.19 owner: `18 passed`;
- all Gate 5 + KT1 architecture: `119 passed`, одна прежняя unrelated
  `DeprecationWarning`;
- architecture authority suite: `29 passed`;
- post-document authority/KT1/G5.20 replay: `65 passed`, та же warning;
- focused Ruff check/format и `py_compile` для G5.20 module/test: passed;
- package `__init__` import/export proof: passed; его полный baseline Ruff scan
  отдельно показывает прежние unrelated F401 export warnings и не
  исправлялся этим Goal;
- copied-package closed-world import: passed; `5` capabilities, exact payload
  hash и G5.20 trial identity;
- `FACTORY_REQUIRED`/`FORBIDDEN` anchors: present and test-covered;
- maintained transport/runtime bypass hits: `0`;
- candidate privacy scan: passed; local path/history/secret-like/replacement
  character hits: `0`.

Одна closed-world команда была отклонена shell policy до выполнения из-за
recursive temp cleanup. Повтор без cleanup реально выполнил isolated import;
это invocation-policy abort, не assertion failure.

## Stop / next allowed boundary

`G5.20_PARTIALLY_PROVEN`; зависимый runtime slice не начат.

Следующая допустимая граница требует отдельной явной авторизации: уточнить
только generic authoring contract/context для static metadata, typed wrapper
inputs и gap-type invariants, затем провести новый независимый trial. Этот
результат не даёт оснований добавлять Section 2 capability или behavior.
