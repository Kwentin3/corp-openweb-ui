# G5.19 — Independent Discovery Report

Дата: 2026-08-10

Статус: `NOT_PROVEN`

Product status: `INACTIVE PROOF`; activation отсутствует.

## Итог

На финальный вопрос G5.19 пока нельзя честно ответить ни «да», ни «нет».

Clean-context LLM не получила возможности выполнить authoring: оба отдельно
замороженных запроса были отклонены strict-output adapter до inference. Поэтому
нет model response, Declaration Definition candidate, compilation/gap report и
semantic model verdict.

Доказан более узкий отрицательный результат:

> текущий neutral output schema несовместим с выбранным strict-output provider
> profile; проблема находится на authoring boundary, а не в runtime.

## Context bootstrap

- Домен: inactive Gate 5 Declaration Definition authoring trial.
- Current owners: G5.16 official evidence; G5.18 capability v1/behavior registry;
  G5.8 methodology authority; G5.12 projection owner.
- Новый sole owner: `Gate5CleanContextDeclarationTrialFactory.create`.
- Provider call не стал product/control/smoke path.
- Compatibility: G5.16 candidate/validator и capability v0 не менялись.
- Документация: новый v0 trial contract и authority-map row.
- Runtime semantics, capabilities, behaviors и artifacts не менялись.
- Новая параллельная execution authority не создана.

## Что декларация попросила?

В clean payload вошёл тот же bounded official FNS context для 3-НДФЛ 2025:

- identity формы, порядка, electronic format и XSD;
- securities-disposal occurrence Appendix 8 и пять стабильных semantics;
- operation code `01` для указанного bounded profile;
- требования Section 2 по income group, totals, deductions, accepted expenses и
  tax-base calculation structure.

Official evidence не помечал какой-либо requirement как «ожидаемый следующий
gap». Термин `line 060` присутствовал только внутри official evidence, что
разрешено G5.19.

## Что clean LLM поняла, что runtime уже умеет?

Неизвестно: inference не начался.

Repository truth, который был доступен модели, прошёл deterministic local
validation и включал ровно пять proven case-time capabilities v1, в том числе
`execute_published_typed_behavior_v1`, две exact registered behavior pairs и
validated Appendix 8 projection. Но нельзя приписывать модели выводы, которых
она не вернула.

## Какой исполнимый кусок она собрала?

Никакой. Response artifact отсутствует, candidate не создавался вручную и не
восстанавливался из G5.16.

Это не опровергает существующую repository composition
`typed execute -> operation model -> aggregate`; G5.18 уже доказал её отдельно.
G5.19 не доказал, что clean author способен самостоятельно её вывести.

## Где и почему trial остановился?

### Frozen attempt 001

```text
trial id       g5.19-primary-2026-08-10-001
payload bytes  27203
payload sha256 ae914005980d286b531a57b4d667684b35e21751f0bd0022019e362be389e749
result         rejected_before_inference
error          invalid_json_schema: uniqueItems is not permitted
response       absent
```

Payload не исправлялся под тем же identity. В соответствии с freeze rule была
создана отдельная identity.

### Frozen attempt 002

Единственным content change было удаление unsupported `uniqueItems`; evidence,
capabilities, inventory и authoring instructions не менялись.

```text
trial id       g5.19-primary-2026-08-10-002
payload bytes  27013
payload sha256 a3ad620016c93eff08a7f79cdb24f86cdcc81b0dd16ce7a68be2660d760fac46
result         rejected_before_inference
error          invalid_json_schema: nested const schema requires explicit type
response       absent
```

Третий call не выполнялся: это уже стало бы iterative schema fitting до
желаемого ответа, что запрещено anti-cherry-picking boundary G5.19.

## Как классифицировать остановку?

Это не declaration gap из taxonomy
`missing_runtime_capability / missing_published_behavior / missing_artifact /
unsupported_value_kind / missing_evidence / incompatible_contract`.

Это experiment-boundary failure:

```text
strict_output_schema_provider_profile_compatibility
```

Официальная OpenAI документация подтверждает, что Structured Outputs принимает
subset JSON Schema и strict request с неподдерживаемой схемой завершается
ошибкой. Проверено 2026-08-10:
[Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## Совпал ли вывод с repository truth?

Для Declaration Definition candidate сравнивать нечего.

Deterministic repository checks до call подтвердили:

- payload содержит Runtime Capability Contract v1 projection;
- capability IDs существуют и имеют `proven/case_time` status;
- methodology identities/hash bindings разрешаются existing authority;
- registered behavior/input/output pairs разрешаются static registry;
- projection identity разрешается existing G5.12 owner;
- neutral validator не содержит expected concrete requirement/gap;
- unknown capability, artifact и behavior-contract mismatch fail closed.

Provider errors показали отдельный недостаток: Draft 2020-12 schema validity не
равна совместимости с конкретным strict-output profile. Именно этот preflight
отсутствовал.

## Был ли gap подсказан модели?

Semantic gap не был ни подсказан, ни обнаружен: inference отсутствовал.

Поэтому требуемый для успешного blind proof ответ `нет` здесь неприменим и не
подменяется ложным pass.

## Blind Trial Record

Safe record:
`BROKER_REPORTS_GATE5_CLEAN_CONTEXT_DECLARATION_AUTHORING_G5_19.blind-trial.safe.json`.

Итоговые счётчики:

```text
provider requests             2
completed inference calls     0
model responses               0
structured candidates         0
manual candidate repairs      0
within-trial retries           0
semantic validator            not_run
post-hoc candidate comparison not_applicable
```

Exact stderr сохранён только во внешнем temp evidence: он повторяет полный
provider-visible payload и не нужен в Git. В Git находится только safe error
projection без credentials, private values и local paths.

## Context measurement

| Section | G5.16 bytes | G5.19 attempt 002 bytes | Delta |
| --- | ---: | ---: | ---: |
| system instructions | 832 | 1,140 | +37.0% |
| research policy | 593 | 656 | +10.6% |
| runtime capabilities | 6,775 | 7,461 | +10.1% |
| published artifact inventory | 1,785 | 5,644 | +216.2% |
| official evidence | 4,528 | 4,528 | 0.0% |
| output schema | 1,097 | 7,447 | +578.9% |
| total envelope | 15,747 | 27,013 | +71.5% |

Token proxy G5.19: `6,754` (`UTF-8 bytes / 4`). Capability Contract v1 не
начал раздуваться: его рост всего `686` bytes. Основной рост — полноценная
machine schema и typed artifact inventory. Оптимизация размера сейчас не нужна;
активная проблема — provider-profile schema compatibility.

## Audit G5.16 validator

G5.16 validator не был reused, потому что он:

- использует capability v0 resolver;
- требует specific `first_runtime_composition_gap_id`;
- требует specific `first_downstream_declaration_gap_id`;
- требует заранее определённый `missing_runtime_capability` для первого поля.

Новый validator проверяет только closed schema, official refs, current v1
capabilities, published artifacts, exact behavior pairs, I/O compatibility и
cross-reference consistency. Он принимает иной unpublished behavior ID и не
содержит Section 2/group-tax-base expectation.

## GUI hypothesis

Схема

```text
chat authoring -> candidate -> deterministic validation -> human review
```

остаётся архитектурно реалистичной, но G5.19 не дал более сильного подтверждения,
чем G5.16. До model inference не дошло. GUI по-прежнему может быть нужен для
review/diff/publish; вывод «GUI больше никогда не нужен» не сделан.

## KISS

Добавлены только:

- один payload/neutral-validator owner;
- два immutable frozen payload attempts и safe plans;
- один safe blind-trial record;
- focused tests;
- versioned contract, authority row и этот report.

Не добавлены workflow engine, Declaration runner, DB, capability, tax behavior,
methodology, product UI или activation.

## Validation

PowerShell, explicit `PYTHONPATH`, terminal outcomes:

- focused G5.19: `12 passed`;
- all Gate 5 + KT1 architecture: `113 passed`, `1` unrelated existing
  `DeprecationWarning`;
- authority/KT1/G5.19 combined replay: `59 passed`, та же warning;
- architecture authority suite: `29 passed`;
- Ruff check: passed;
- Ruff format check: passed;
- `py_compile`: passed;
- copied-package closed-world import/factory resolution: passed, `5`
  capabilities, exact payload hash `a3ad6200…fac46`;
- all frozen/safe JSON: parsed;
- Russian report UTF-8/Cyrillic and replacement-character scan: passed;
- targeted secret-like scan and whitespace/diff checks: passed.

Одна промежуточная команда передала PowerShell wildcard в `pytest` буквально и
завершилась `no tests ran`; это runner invocation error, не assertion failure.
Она была заменена explicit PowerShell file-array invocation, после чего suite
реально выполнил `113` тестов.

## Stop / next allowed boundary

`G5.19_NOT_PROVEN`; dependent engineering slice не начат.

Следующий clean-context call не разрешён этим отчётом. Для него нужна отдельная
явная авторизация после появления deterministic preflight, проверяющего exact
JSON Schema subset выбранного provider/profile до freeze и provider request.
Runtime до этого менять нельзя.
