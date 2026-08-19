# Broker Reports Gate 5 Mission Context Effect Verification — G5.28A.1

Date: `2026-08-10`

Status: `G5.28A.1_CLOSED`

Verdict: `MISSION_CONTEXT_NEUTRAL`

Corrected G5.28 trial: `NOT_RUN`

G5.29 / product runtime: `NOT_STARTED / NOT_ALLOWED`

## Answer

Короткий рассказ о конечном pipeline не дал устойчивого улучшения grouping
same-policy semantic obligations.

Оба варианта получили одинаковые official evidence, 25 reviewed obligations,
policy definitions, component inventory, local grouping principles, output
contract, model/profile и clean execution settings. Единственным изменением в
Variant B был 743-byte mission block.

Результат:

```text
                              Variant A       Variant B
hard validator pass             3 / 3           3 / 3
raw blinded defects             3, 5, 6         4, 6, 5
median raw defects                  5               5
target-layout defects               0               0
invented execution defects          0               0
```

Mission context изменил несколько конкретных merges, но не сделал границы
стабильно лучше и не снизил consumer-fit defects. Одновременно он не вызвал
устойчивого premature runtime design. По заранее зафиксированному правилу это
`MISSION_CONTEXT_NEUTRAL`.

Для будущего G5.28B полный блок `FINAL GOAL → Scope Resolver → Declaration
Model → PROJECT` не нужен. Достаточно оставить короткие локальные boundary
constraints:

```text
one honest applicability question for the case and period
one coherent typed semantic component family
one identical closed applicability policy per domain
target-independent; no runtime or projection behavior
```

Это подтверждает: `clean context != context-free`, но полезен именно минимальный
consumer boundary, а не история всего downstream pipeline.

## Controlled design

До любого успешного inference были заморожены:

- budget `3 A + 3 B`;
- порядок запуска `A1, B1, A2, B2, A3, B3`;
- exact shared input и два exact prompt hashes;
- один model/profile: `gpt-5.6-sol / high`;
- новые пустые cwd, `read-only`, ephemeral session, ignored config/rules;
- `history=0`, `retry=0`, `follow-up=0`, `repair=0`;
- одинаковый hard validator;
- SHA-sorted blinded review `R1...R6`;
- verdict rule и четыре defect categories.

Budget `3+3` выбран как минимальный из разрешённых, который показывает
within-variant stability. Один ответ против одного был бы слишком шумным.

Preregistration:
[`preregistration.v1.safe.json`](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.preregistration.v1.safe.json).

```text
preregistration SHA-256
34a43042bf96bb035497cc2544aaf136844433d74ef953c04a09a92c38d0cde9
```

## Exact input isolation

Shared input:

```text
official surfaces       14
reviewed obligations    25
policies                 5 closed IDs
component contracts      4 bounded-only IDs
shared-input SHA-256     dd72c7e725f4fae0df4543c2492743f767ba4f4162004f90249045ad95e3ce0a
```

Variant A:

```text
base prompt + shared input
bytes   19056
SHA-256 8213e22d1ce816ffdcbe0da93224fe19e21614d9584eff0d69c657783123f9c4
```

Variant B:

```text
base prompt + mission context + shared input
bytes   19800
SHA-256 65cc4a055ec29e3d0f84c5482d2b0aa1faaf6f1cdf5eec2fca03af22aa64b717
```

Only inserted resource:

```text
mission-context bytes   743
mission-context SHA-256 bd2c05ded1d681db3e3a16b82078bbf8cd0cbcf787add56d9e77de00e96b56a0
```

Mission block сообщал назначение domains, downstream applicability decision,
typed component и separate projection. Он не содержал прежний candidate,
ошибочный domain, expected split/IDs/count, validator findings, roadmap или
конкретный известный failure.

Official package оставался связан с актуальной формой по [приказу ФНС России
от 20.10.2025 № ЕД-7-11/913@](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
и [странице форм 3-НДФЛ](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/).
Эксперимент использовал уже проверенные exact source hashes; никакой model не
извлекал obligations заново.

## Holdout pressure

Пакет не был подогнан только под professional-activity failure. В нём были:

| Pattern | Evidence in package |
| --- | --- |
| mandatory aggregate | filing/taxpayer/signer; income-group base + settlement |
| same-policy but different purpose | declaration budget disposition versus group calculations |
| factual occurrence | Russian-source and foreign-source income |
| different-policy meanings | professional activity classification versus elective professional deductions |
| elective aggregates | professional, personal, property-acquisition deduction claims |
| typed aggregate pressure | property/vehicle/gift and securities/digital-assets/partnership results |

Different-policy merge был закрыт deterministic validator. Экспериментальная
работа модели оставалась только над same-policy boundaries.

## Protocol recovery disclosed

Первый v0 transport protocol не дал ни одного model-authored output:

1. Один local launcher завершился до `codex`, потому что Windows PowerShell
   `ProcessStartInfo` не предоставил `ArgumentList`.
2. `A1`, `B1` и диагностический `A2` получили provider `400
   invalid_json_schema`: у `schema_version` с `const` не был указан `type`.
3. Candidate files и usage отсутствовали; model inference не состоялся.

v0 не смешивался с experiment results. После failure attribution был отдельно
заморожен v1 protocol. В v1 provider response-format enforcement убран:
strict JSON остался наблюдаемым authoring outcome и проверялся одинаково после
freeze. Candidate contract в prompt не менялся между A и B.

Перед A2/B2 v1 был ещё один local shell abort: helper `H` разрешился как
PowerShell alias `Get-History`. Ни один процесс не стартовал; frozen inputs не
менялись. Все такие failures сохранены, а не выданы за inference.

## Six authoring outcomes

Все заранее назначенные v1 calls завершились один раз. Candidate bytes не
редактировались.

| Call | Exit | Seconds | Candidate bytes | Domains | Output / reasoning tokens | SHA-256 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| A1 | 0 | 63.166 | 8,826 | 19 | 2,581 / 698 | `3609ba8050368471cc2b81343857e9bee66f5a311ff9cb7c61f424c8a5cadcb3` |
| A2 | 0 | 59.215 | 7,332 | 14 | 2,462 / 927 | `45089509beb969f4fd7e957fb08b490c55fb3d80f58cfa12eceeee70007e7947` |
| A3 | 0 | 84.474 | 6,762 | 13 | 3,120 / 1,681 | `88ecef078419f5784473888c28427391c1d51e1c9d2ab29659eb51ec77f0023d` |
| B1 | 0 | 66.551 | 8,522 | 18 | 2,859 / 1,034 | `12a612d14647ff21d8028c1be75dc38e15611b4c64fff65e2e9eded6a3aa2073` |
| B2 | 0 | 77.909 | 6,399 | 11 | 3,667 / 2,327 | `dc38c0e46aa0dd1cec5ddad739c5ce195eedbfdd2a05b40ed0292d394d55cfb3` |
| B3 | 0 | 84.458 | 7,678 | 15 | 3,293 / 1,680 | `cb4966ef67baa2ea1afcb5a82b7be584a56c4fa8b1b98df3b1f43026e1722452` |

Domain count не использовался как score. Его широкий диапазон внутри обоих
variants сам по себе показывает, почему expected count не должен становиться
answer key.

Raw candidates:

- [`A1`](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.candidate.v1.A1.json),
  [`A2`](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.candidate.v1.A2.json),
  [`A3`](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.candidate.v1.A3.json);
- [`B1`](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.candidate.v1.B1.json),
  [`B2`](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.candidate.v1.B2.json),
  [`B3`](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.candidate.v1.B3.json).

## Identical deterministic validation

Validator действительно исполнился в explicit Windows PowerShell → Python 3.11
context и завершил проверки, а не только вернул green status. Первый launch
validator был abort до проверки из-за Cyrillic absolute path; повтор использовал
`Path.cwd()` и относительные пути без изменения правил.

Для каждого candidate проверены observable invariants:

- strict UTF-8 JSON object, duplicate-key and non-finite rejection;
- exact root/domain/component schemas;
- all 25 obligations exactly once;
- no unknown/duplicate/empty refs;
- one identical policy per domain;
- exact component contract allowlist and no `published_exact` overclaim;
- bounded contract semantic-scope checks;
- no target-layout or invented execution language.

```text
strict candidate JSON                 6 / 6 PASS
25 exact obligation refs              6 / 6 PASS
mixed-policy domains                  0
unknown or duplicate refs             0
invented/overclaimed contracts        0
target-layout grouping                0
invented execution semantics          0
```

Irreversible boundary для этого research flow — freeze raw candidate bytes.
Все validation/review выполнялись после freeze и не могли изменить output.

## Blinded consumer-fit review

Candidates были отсортированы по ascending SHA-256 и получили aliases R1–R6.
Reviewer видел obligations, policies, components, mission contract и пять
одинаковых вопросов, но не видел call/variant mapping. Один clean review turn
вернул strict JSON:

```text
review bytes   10926
review SHA-256 8da4c5ecf2ac74eb486f9e33d010b20fadbe9ac224e717067340e504ad835c6d
structure      PASS: R1..R6 exactly once, domain refs and counts valid
```

Во время этого одного turn transport сделал внутренний reconnect после
WebSocket reset. Агент не запускал второй review, retry или repair; итоговый
turn завершился exit 0.

После freeze mapping был раскрыт:

| Alias | Call | Raw defects | Target layout | Invented execution |
| --- | --- | ---: | ---: | ---: |
| R1 | B1 | 4 | 0 | 0 |
| R2 | A1 | 3 | 0 | 0 |
| R3 | A2 | 5 | 0 | 0 |
| R4 | A3 | 6 | 0 | 0 |
| R5 | B3 | 5 | 0 | 0 |
| R6 | B2 | 6 | 0 | 0 |

```text
A raw values  3, 5, 6   median 5
B raw values  4, 6, 5   median 5
```

Raw review:
[`review.blinded.v1.json`](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.review.blinded.v1.json).

### Review limitation

Raw review systematically назвал unsafe любое объединение independently
optional members. Это слишком сильное правило. G5.28A уже установил:

> Different internal life states do not force a root split when the domain has
> an honest `any member applies` decision and one coherent aggregate component
> retaining internal variants and completeness.

Поэтому абсолютные raw defect counts нельзя повышать до architecture truth.
Например, reviewer отклонил professional-deduction pair,
property-acquisition/interest и property/vehicle aggregates во всех случаях,
хотя candidate
meanings не утверждали одновременное наличие каждого member.

Raw review не переписывался и score post-hoc не пересчитывался. Для A/B verdict
это не меняет результат: одинаковый bias применён ко всем candidates, а median
осталась `5 == 5`. Отдельный bounded audit нашёл только один явный one-off
pressure: B2 присоединил taxable gifts к disposition component, хотя gift не
имеет общей proceeds/basis structure. Это не повторилось в B1/B3 и не выполняет
preregistered harmful rule.

## Boundary stability matrix

Частота означает, что obligations оказались вместе в одном domain. Это
диагностика, не expected partition.

| Merge pattern | A | B | Reading |
| --- | ---: | ---: | --- |
| filing + taxpayer + signer | 3/3 | 3/3 | stable without mission block |
| income-group base + settlement | 3/3 | 3/3 | stable without mission block |
| declaration budget + income-group results | 0/3 | 2/3 | mission-specific broader grouping, not independently proven better |
| Russian + foreign source income | 1/3 | 2/3 | unstable in both variants |
| civil + author professional deductions | 3/3 | 3/3 | stable without mission block |
| all four personal-deduction families | 2/3 | 1/3 | mission did not improve aggregate stability |
| property + vehicle dispositions | 3/3 | 3/3 | stable without mission block |
| gift + property/vehicle dispositions | 0/3 | 1/3 | one-off B overmerge pressure |
| acquisition + interest deductions | 3/3 | 3/3 | stable without mission block |
| securities + digital assets + partnership | 2/3 | 2/3 | equal |

Основные coherent boundaries уже получались из obligation semantics и local
principles. Mission paragraph не дал повторяемого улучшения на holdouts.

## Verdict rule application

`MISSION_CONTEXT_HELPFUL` не выполнен:

- hard pass rate не хуже, но median defects не ниже;
- устойчивого улучшения merge patterns нет.

`MISSION_CONTEXT_HARMFUL` не выполнен:

- hard pass rate и median не хуже;
- target-layout и invented-runtime defects не появились;
- one-off questionable merge не повторился в двух B candidates.

Следовательно, по preregistration:

```text
MISSION_CONTEXT_NEUTRAL
```

## Exact G5.28B context contract

Future clean authoring должен использовать task-only context и reviewed
obligation package. Постоянный prompt содержит только:

```text
TASK
Group reviewed target-independent semantic obligations into root domains.

BOUNDARY
Each domain has one honest applicability question for the case and period.
Each applicable domain resolves one coherent typed semantic component family.
All member obligations use one identical closed applicability policy.
The boundary remains meaningful when XML/PDF layout changes.

NON-GOALS
No tax calculation, runtime workflow, case-time legal reasoning,
human questions or XML/PDF projection.
```

Не добавлять:

- полный `FINAL GOAL` pipeline narrative;
- имена Scope Resolver, complete Declaration Model или PROJECT как motivation;
- историю Gate 5, G5.28 candidate/failure или roadmap;
- expected domain list, IDs, count или partition.

Таким образом, минимальный context не равен нулю: он сообщает contract самой
границы. Дополнительная mission story доказанной ценности не показала.

## Delivered evidence

- [shared official/obligation input](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.shared-input.safe.json);
- [base task-only prompt](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.base-prompt.safe.txt);
- [isolated mission block](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.mission-context.safe.txt);
- [post-response candidate schema](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.output-schema.v1.safe.json);
- [v1 preregistration](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.preregistration.v1.safe.json);
- [machine-readable experiment record](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.experiment.safe.json);
- [raw blinded review](./BROKER_REPORTS_GATE5_MISSION_CONTEXT_EFFECT_G5_28A_1.review.blinded.v1.json).

The invalid v0 response schema and its frozen preregistration are retained as
transport evidence; neither is a trusted candidate schema or experiment result.

## Scope stop

В G5.28A.1:

- G5.28 candidate не исправлялся;
- Declaration Definition не публиковалась;
- production/runtime code и capabilities не менялись;
- Scope Resolver, human questions, Tax Models, Declaration Model, tax payable,
  XML/PDF не создавались;
- commit, push и PR не выполнялись.

Следующая допустимая граница — отдельный G5.28B clean authoring trial с exact
minimal local context contract. `G5.29` остаётся запрещён.
