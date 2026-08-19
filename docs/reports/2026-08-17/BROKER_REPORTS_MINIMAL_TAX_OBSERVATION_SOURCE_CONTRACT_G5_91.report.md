# G5.91 — Minimal Tax Observation Source Contract

Дата: 2026-08-17
Режим: inactive source-contract qualification
Verdict: `DESIGN_STOP`
Terminal: `CURRENT_GATE3_SOURCE_LOCAL_ASSERTION_BOUNDARY_INSUFFICIENT`

## Architecture bootstrap

Current authority восстановлен в порядке `Pipeline Gates -> exact contract ->
factory -> evidence`.

| Boundary | Current owner | Уже умеет | Точный gap |
| --- | --- | --- | --- |
| Gate 3 source meaning | `Gate3FinancialLabelDictionaryFactory.create` | source-local financial type, `TAX_WITHHELD`, sparse omission | нет отдельного broker-stated adjustment meaning |
| Gate 3 literal roles | `Gate3FinancialRolePackFactory.create` | date/amount/currency и другие literal bindings | нет роли для буквальной adjustment wording |
| Gate 4 normalized source fact | `Gate4FinancialCaseMaterializerFactory.create` | переносит published financial type, roles, source literals, canonical target и semantic authority identities | новый type должен иметь published Role Pack profile |
| Gate 5 methodology boundary | current Evidence-to-Tax-Methodology Bridge | различает требуемые methodology inputs и запрещает inference/netting | G5.90 требует сохранить `WITHHOLDING` versus `ADJUSTMENT`, но не публикует adjustment arithmetic |

Named consumer взят только из evidence G5.90: adjustment observation нельзя
молча считать positive withholding/payment evidence. `REFUND`, `REVERSAL` и
`OTHER_ADJUSTMENT` разным downstream behavior пока не соответствуют.

## Минимальный candidate

Аудит отверг отдельный `state/operation` field: current proposal и Gate 4 DTO
его не имеют, поэтому такой вариант менял бы schema, validators и materializer.
Минимальный candidate использует существующий механизм:

```text
Dictionary 2.1.0 (explicit inactive)
  + TAX_ADJUSTMENT

Role Pack 3.1.0 (explicit inactive)
  + source_wording
  + TAX_ADJUSTMENT(date, amount, currency, source_wording; asset optional)
```

Тип не утверждает refund, reversal, netting, period treatment, credit
eligibility или связь с withholding/income. Source-authored direction может
помочь отличить movement, но направление без explicit tax meaning
недостаточно. Dictionary не содержит `US Tax`, broker names или literal rules.

Public Gate 3 persistence и public Gate 4 runtime materialизуют explicit
candidate как `normalized_source_fact` с type, date, amount, currency,
source wording, annotation target, canonical binding и Dictionary/Role Pack
identities. Gate 5 consumer test оставляет такой факт видимым в Gate 4, но не
включает его в `withheld_tax` и налоговую формулу.

## Source-truth qualification

Qualification corpus — immutable G5.88 controls: 105 source-true explicit-tax
credit/return-direction rows, 113 ordinary withholding controls после
исправления frozen oracle, 25 true dividends и 12 structural/nonfinancial
controls. Ни один cycle не использовал VLM, parser change, retry, best-of-N,
broker literal blacklist или tax calculation.

| Cycle | Contract change / route | Adjustment | Wrong dividend | Withholding | Dividends | Structural |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | literal `adjustment` candidate, ordinary current Gate 3 | 0/105 | 86 | 85/113 | 25/25 | 12/12 |
| 2 | source-authored movement direction, ordinary current Gate 3 | 44/105 | 61 | 113/113 | 25/25 | 12/12 |
| 3 | additionally tightened dividend wording | 44/105 | 61 | 104/113 | 22/25 | 12/12 |
| 4 | rollback cycle 3; existing demand-scoped request for `TAX_ADJUSTMENT` | 53/105 | 52 | 113/113 | 25/25 | 12/12 |

Cycle 3 был отвергнут из-за control regression. Cycle 4 — strongest
non-regressing result, но не terminal success: 52/105 остаются систематически
ошибочными `DIVIDEND_INCOME`. Результаты всех cycles сохранены; это не
best-of-N и не повтор одного provider response.

## Design stop

Source evidence достаточно для factual distinction: exact tax meaning и
source-authored cash direction присутствуют. Gate 4 также способен перенести
минимальный candidate. Непройденная граница — current Gate 3 whole-table
source-local proposal: даже с честным type и существующим consumer-demand hint
она продолжает переносить non-dividend tax rows в `DIVIDEND_INCOME`.

Исправление потребовало бы вернуться к source-local assertion packaging,
table-specific one-pass/KISS ветке, prompt tuning либо deterministic literal
guard. Все эти маршруты запрещены G5.91 или выходят за minimal source-contract
scope. Поэтому fail-closed результат:

```text
CURRENT_DEFAULT_DICTIONARY = 2.0.1
CURRENT_DEFAULT_ROLE_PACK = 3.0.0
MANAGED_RUNTIME_PROJECTION = UNCHANGED
PRODUCTION_ACTIVATION = FALSE
```

Explicit candidate resources и Gate 3 -> Gate 4 representability test
сохранены как inactive evidence; они не являются current runtime authority.

## Verification and KISS

- focused + adjacent Gate 3/4/Gate 5/cross-gate suite: `166 passed`;
- post-rollback focused current/candidate suite: `43 passed`;
- managed OpenWebUI asset parity: `--check` passed against current `2.0.1`;
- Ruff, Python compile, JSON parse, UTF-8/Cyrillic/fence checks и
  `git diff --check`: passed;
- current default pointers: Dictionary `2.0.1`, Role Pack `3.0.0`;
- one canonical worktree; branch stayed `0 behind / 15 ahead` of
  `origin/main`; staging, commit, push and production activation: zero.

KISS verdict: сам candidate минимален — один label и одна literal role. Но
активировать его при 52/105 systematic wrong-dividend rows было бы сложнее и
опаснее, чем сохранить current fail-closed contract. Новый framework не создан.

## Terminals

Доказано:

```text
MINIMAL_GATE3_GATE4_CANDIDATE_REPRESENTABILITY_PROVEN
TAX_CONCLUSION_REMAINS_AFTER_GATE4
BROKER_SPECIFIC_RULES_ZERO
INFERRED_RELATIONS_ZERO
TRUE_DIVIDEND_CONTROLS_PRESERVED_IN_FINAL_CYCLE
ORDINARY_WITHHOLDING_CONTROLS_PRESERVED_IN_FINAL_CYCLE
UNMAPPED_FAIL_CLOSED_PRESERVED
```

Не доказано:

```text
BROKER_TAX_OBSERVATION_SOURCE_CONTRACT_PROVEN
WITHHOLDING_VS_ADJUSTMENT_SOURCE_DISTINCTION_PROVEN
SYSTEMATIC_TAX_ADJUSTMENT_AS_DIVIDEND_ERROR_REMOVED
READY_TO_CONTINUE_SOURCE_DATA_PREPARATION
```

Final verdict: `DESIGN_STOP`.

Следующий GOAL не должен расширять tax ontology. Если он будет разрешён, его
предмет — current Gate 3 source-local assertion boundary на уже существующих
owners, с сохранением exact controls и без KISS resurrection или broker rules.

Safe receipt:
`BROKER_REPORTS_MINIMAL_TAX_OBSERVATION_SOURCE_CONTRACT_G5_91.DESIGN_STOP.safe.json`.
