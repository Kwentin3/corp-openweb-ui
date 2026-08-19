# G5.21 — Declaration Authoring Language Report

Дата: 2026-08-10

Статус: `PROVEN`

Product status: `INACTIVE PROOF`; publication/activation нет.

## Итог

Да. Declaration Definition v2 стал достаточно точным языком для независимого
LLM-authoring в проверенном bounded surface.

Новый clean-context candidate прошёл deterministic semantic validation без
изменения bytes, repair, retry или follow-up. Модель использовала только
реальные capability/behavior/artifact identities, отделила runtime support от
неизвестной доступности case inputs и без подсказки нашла первый реальный
blocker: `section2_calculation_behavior_missing`.

Новая runtime capability, behavior, methodology, artifact или tax semantics не
добавлялись. Следующий runtime slice не начат.

## Context bootstrap

- Домен: Gate 5 authoring-only contract refinement.
- Current owner:
  `Gate5DeclarationAuthoringLanguageV2Factory.create`.
- Reused authorities: G5.18 Runtime Capability Contract v1 и typed behavior
  registry, G5.8 methodology artifacts, G5.12 projection artifact, G5.16
  official evidence.
- G5.19/G5.20 payloads, candidate и validators сохранены как historical replay
  evidence.
- Provider invocation остаётся outer experiment infrastructure, не application
  runtime.

## Что было не так в v1

Три G5.20 failure class сводились к одной причине: v1 просил модель повторять
механические факты, которые уже однозначно знает repository code.

1. Target order/period смешивался с producible semantic requirement.
2. Published behavior semantic I/O смешивался с typed-execution wrapper I/O.
3. Gap про отсутствующее behavior требовал ID несуществующего объекта.

Это не исправлялось частными Appendix 8/Section 2 правилами. V2 разделил:

```text
official requirement known
runtime supports
published behavior/artifact exists
case inputs available
```

Model authoring оставляет первые три семантическими, а четвёртое при отсутствии
case evidence получает deterministic `not_evaluated`.

## Минимальный v2

Из model output удалены:

- root status/findings/authoring;
- `end_to_end_available_from_current_case_evidence`;
- boundary inputs;
- declared capability input/output contracts;
- repeated behavior input/output contract IDs;
- synthetic `missing_behavior_id`, `missing_contract_id` и
  `missing_artifact_kind`.

Composition теперь содержит capability identity, optional behavior identity и
artifact identities. Обычный compiler восстанавливает exact wrapper I/O,
registered behavior I/O, aggregate definition status и case-input assessment.

Это schema+compiler boundary, не новый framework или DSL.

## Frozen clean input

```text
trial id       g5.21-primary-2026-08-10-001
payload bytes  24971
payload sha256 90294e3cbecb8c273db51271646dbc9b6281e4db8f2a8d62bcf16a3571633787
sections       6
history        none
bias audit     passed
```

G5.20 candidate, validator errors, expected answer/gap и roadmap модели не
передавались. Bias audit допустил только `line 060` внутри official evidence.

До provider call один preflight wrapper исказил кириллический absolute payload
path и остановился на локальном `read_bytes`. `codex` не запускался,
semantic attempt/candidate не возникли. Затем использован relative path из
фиксированного cwd; frozen bytes и invocation profile не менялись.

## Единственный inference

```text
provider       openai_codex_cli
client         codex-cli 0.147.0-alpha.6.5
model          gpt-5.6-sol
reasoning      high
session        new ephemeral
workspace      empty temporary directory
sandbox        read-only
provider schema none
provider calls 1
semantic attempts 1
retry/follow-up/repair 0/0/0
elapsed        119.593 s
return code    0
```

Final-message capture:

```text
response bytes   10209
response sha256  8cde1468c6a37917432ec5f6f1c0412107093b2c6d339f64fa8d8d2fe29277fe
JSON parse       passed
closed schema    passed
semantic compile passed
privacy scan     passed
```

Candidate скопирован в evidence byte-identical; выбирать лучший из нескольких
ответов было невозможно и не требовалось.

## Что независимо нашла модель

Поддержаны две requirements:

- `appendix8_category_semantics` через required-values resolution, exact
  published operation-model behavior и category aggregation;
- `appendix8_declaration_occurrence` через существующий validated Appendix 8
  projection.

Unsupported surface:

- `section2_group_tax_base`;
- `electronic_group_bound_document`.

Первый blocker — `section2_calculation_behavior_missing`. Дополнительно модель
отделила `section2_projection_artifact_missing` и
`full_electronic_contract_incompatible`. Эти identifiers не присутствовали в
payload. Обоснование совпадает с repository truth: существующие operation model
и category aggregation дают securities sub-semantics, но не полный Section 2
group calculation; Appendix 8 projector не является Section 2/full-XSD
projector.

## Deterministic compilation

```text
definition status       partially_compilable
case input assessment   not_evaluated
requirements            4
supported/unsupported   2/2
resolved compositions   7
typed gaps              3
manual repairs          0
```

Compiler сам разрешил exact capability inputs/outputs и registered behavior
contracts. Candidate не повторял Python wrapper signature и не создавал
missing-object IDs.

## Evidence

- frozen plan:
  `BROKER_REPORTS_GATE5_DECLARATION_AUTHORING_LANGUAGE_G5_21.plan.safe.json`;
- exact model result:
  `BROKER_REPORTS_GATE5_DECLARATION_AUTHORING_LANGUAGE_G5_21.candidate.json`;
- deterministic compiler result:
  `BROKER_REPORTS_GATE5_DECLARATION_AUTHORING_LANGUAGE_G5_21.compilation.safe.json`;
- aggregate trial receipt:
  `BROKER_REPORTS_GATE5_DECLARATION_AUTHORING_LANGUAGE_G5_21.trial.safe.json`.

Hashes are bound inside the trial receipt. Candidate privacy scan found no
private keys, provider/GitHub/AWS tokens, email, UNC or Windows absolute path.

## Validation

Targeted language plus historical clean-context tests:

```text
36 passed
Ruff passed
```

Полный проверенный contour:

- all Gate 5 modules + KT1 architecture: `137 passed`, одна прежняя unrelated
  `DeprecationWarning`;
- gate architecture + type-first architecture audit: `42 passed, 1 skipped`;
- final post-document v2/KT1/architecture replay:
  `78 passed, 1 skipped`, та же warning;
- deterministic architecture builder `--check`: passed, `runtime_changes=0`,
  `provider_calls=0`, `historical_files_modified=0`;
- focused Ruff, format и `py_compile`: passed;
- copied-package closed-world import: passed; exact v2 payload hash и все пять
  capability records доступны без workspace-only dependency;
- `FACTORY_REQUIRED`/`FORBIDDEN`, no-transport/no-runtime checks: test-covered;
- candidate privacy scan: passed.

После осознанного изменения current authority map architecture replay
fail-closed обнаружил старый authorized successor SHA. Pin приведён к exact
repository-LF-normalized hash, который использует существующий audit; raw
Windows line endings не стали отдельной authority. Owner/status/behavior не
менялись. Повторный builder и suite прошли. Transport success не используется
как semantic proof.

## Verdict

`G5.21_PROVEN`.

Проверенная LLM независимо сформировала валидный semantic Definition, нашла
реальную supported Appendix 8 поверхность и реальный следующий gap. Exact
mechanical binding выполнен deterministic ordinary code, а не моделью.

Доказательство bounded: оно не утверждает taxpayer completeness, наличие
case-time inputs, Section 2 tax logic, full declaration execution или generic
authoring для иных форм.

## KISS-check

- Один текущий v2 owner; v1 сохранён только для replay.
- Удалены неоднозначные и дублирующие поля.
- Механические контракты derived из существующих owners.
- Нет нового runtime, DSL, workflow, DB или product route.

## Hard stop

G5.21 не разрешает Section 2 implementation, новую capability/behavior/artifact,
исполнение candidate, Declaration runner, XML/PDF, publication, GUI, activation
или следующий runtime slice.

Официальная документация проверена 2026-08-10: final-message capture и provider
output schema являются разными CLI seams, а Structured Outputs поддерживает
подмножество JSON Schema:
[Codex developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli),
[Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
