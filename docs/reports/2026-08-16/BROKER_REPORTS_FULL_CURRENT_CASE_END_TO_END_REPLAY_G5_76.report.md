# G5.76 — Full Current-Case End-to-End Replay

## Итог

Текущий реальный кейс не готов к выпуску декларации. Это корректный fail-closed результат: система дошла до Gate 5 и Declaration Preparation, сформировала точные demands и не выпустила синтетический XML/PDF.

Первый внешний для runtime стоп — четыре обязательных USER/CASE факта: подтверждённая личность налогоплательщика, evidence резидентства, подписант/представительство и identity экземпляра декларации. Даже после их получения останутся реальные source-evidence и methodology gaps, перечисленные ниже.

Терминал:

```text
CURRENT_REAL_CASE_END_TO_END_BLOCKED_WITH_EXACT_DEMANDS
ALL_BLOCKERS_CONSUMER_CLASSIFIED
NO_UNJUSTIFIED_SOURCE_LAYER_WORK_OPENED
CURRENT_CASE_READY_UP_TO_FIRST_EXTERNAL_OR_USER_OR_METHODOLOGY_BOUNDARY
```

## Что было заморожено

- 4 реальных PDF; их SHA-256 совпали с `source_sha256` активных Canonical.
- Target: `ru_3ndfl_2025`.
- Trusted USER/CASE inputs на freeze отсутствовали.
- Current store, code/contract и methodology hashes сохранены в приватном bundle.
- Freeze manifest SHA-256: `7e1c3407330f4dea5874d9db9a35e22b46cd060e1146a330ba0cd2e581abe372`.

Набор документов после первого результата не менялся. Приватные значения и PDF в Git не добавлены.

## Реальный маршрут

Первый deterministic resume справедливо отверг старые Gate 3 sidecars: их instruction/dictionary/role-pack уже не соответствовали текущим owners. После этого выполнен один чистый current Gate 3 replay через существующий маршрут: `15` последовательных вызовов `models/gemini-3.5-flash`, retry/repair/fallback/best-of-N = `0`, все `4/4` документов завершены.

Gate 1 normalization не перестраивалась с нуля: replay продолжил активный Canonical только после точной проверки raw SHA-256 → active Canonical binding. Старый research output authority не использовался.

| Этап | Статус | Результат / blocker | Владелец |
| --- | --- | --- | --- |
| RAW → Gate 2 / Canonical | READY (current binding) | 4/4 raw SHA совпадают; clean-from-zero normalization не заявляется | Canonical owner |
| Adaptive Context → Gate 3 | READY | 4/4 current sidecars, 391 annotations | Gate 3 owners |
| Gate 4 | READY | 391 facts; 329 role-complete; 62 incomplete | Gate 4 factory/materialization |
| Gate 5 | BLOCKED | 9/9 active demands blocked; calculations 0 | Gate 5 assembly + methodology/evidence owners |
| Declaration Semantics | PRECONDITION BLOCKED | sealed semantic input отсутствует | Declaration semantic-input owner |
| Release / Completeness | BLOCKED | 12 обязательных actions | Declaration Preparation / release boundary |
| Projection / XML / PDF | NOT ENTERED | projection не имеет права додумывать semantics | Projection owner |

## Что нужно для декларации

| Что нужно | Статус | Что мешает | Владелец |
| --- | --- | --- | --- |
| Current financial source inventory | READY | 391 facts из 4 документов | Gate 4 |
| Налоговый basis по 4 security groups | BLOCKED | в замороженном наборе нет acquisition quantity evidence | SOURCE_DOCUMENT / additional-document demand |
| 13 source facts | BLOCKED | raw/Canonical literals есть, но role binding потерян или создана пустая duplicate annotation | Gate 3 → Gate 4 binding contract |
| 3 source facts | BLOCKED | literal есть, но знак/currency decoration не нормализованы в Decimal contract | Source normalization contract |
| FIFO rounding | BLOCKED | точное правило не формализовано | Versioned methodology |
| Identity, residency, signer, filing instance | BLOCKED | trusted factual evidence отсутствует | USER/CASE human adapter |
| Declaration semantics и release | BLOCKED | upstream demands не terminal | Semantic-input / release owners |

### SOURCE FACT GAP: обязательное разделение

- `SOURCE DOES NOT HAVE IT`: 4 acquisition-quantity blockers. В raw/Canonical для этих групп представлены disposal/charge assertions, но не explicit acquisition rows; Gate 4 также не содержит matching purchase facts. Это реальная нехватка supplied evidence, а не повод улучшать parser.
- `SOURCE HAS IT → pipeline lost`: 13 `required_role_missing`. Literal виден на привязанном Canonical target, но роль не дошла до пригодного Gate 4 value.
- `SOURCE HAS IT → normalization lost`: 3 `decimal_invalid`. Literal сохранён, но consumer не принимает decorated/sign-bearing value как Decimal.

Последние 16 incidents классифицированы только как `SOURCE FACT GAP / SOURCE HAS IT`; второй раз в `MODEL / CONTRACT GAP` они не считаются.

## Готово сейчас

- Current Gate 3 и Gate 4 replay: `4` sources, `391` facts.
- `96` security facts: `80` готовы как source facts, `16` недостаточны.
- Commission assertions: `160` detail + `5` aggregate; withheld-tax assertions: `37` detail + `4` aggregate.
- Invented facts = `0`; invented relations = `0`; reconciliation не выполнялась.
- Declaration Preparation сформировала `12` required actions: `4` USER_FACT, `7` ADDITIONAL_DOCUMENT, `1` METHODOLOGY_RESEARCH.

## Не хватает сейчас

- Четырёх обязательных USER/CASE facts.
- Acquisition evidence для четырёх security groups.
- Одного формализованного FIFO-rounding rule.
- Исправления 13 role-binding и 3 decimal-normalization incidents, только если после закрытия внешних gaps они остаются consumer-blocking.

## Не является blocker

- Универсальный metadata-region selector.
- Номер счёта, номер договора, broker label и прочие supporting metadata без named calculation/scope consumer.
- Budget disposition: текущий action `DEFERRED`, а не first blocker.

## Единственная локальная правка

В first-execution receipt существующего source replay добавлено `provider_rerun_count = 0`. Downstream G5.40F уже требовал это поле; inference, tax logic, metadata и contracts не менялись. После правки весь deterministic downstream был перепроигран.

## Проверки

- `py_compile`: passed.
- `ruff`: passed.
- Focused Gate 3/Gate 5/architecture suite: `58 passed`.
- G5.75 architecture guards: `6 passed`.
- Holdout A: `39 → 39`, exact SHA equality.
- Holdout B: `129 → 129`, exact SHA equality.

39/129 проверены через нормативный `Gate4FinancialCaseRuntimeFactory.create.rebuild_case` на frozen clock до записанного TTL. На текущем live clock артефакты canary уже expired, поэтому operational-live freshness не заявляется; это expiry evidence, не регрессия кода.

## Следующий разрешённый GOAL

Только закрытие первого внешнего boundary: получить через существующий USER/CASE human adapter четыре обязательных factual inputs. Не активировать metadata/VLM и не начинать source-layer research. После factual intake — повторить deterministic downstream; оставшиеся additional-document и methodology demands должны сохраниться fail-closed.

Приватный evidence bundle: `external_private_evidence` (вне Git). Safe machine receipts лежат рядом с этим отчётом.
