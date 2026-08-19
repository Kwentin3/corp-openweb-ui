# G5.70 — VLM-First Metadata Microstand

Дата: 2026-08-16

Статус: `CLOSED_MICROSTAND_PROVEN_RESIDUAL_SEMANTIC_ERRORS_LOCALIZED`

## Terminal

```text
VLM_FIRST_METADATA_MICROSTAND_PROVEN
VISUAL_LAYOUT_METADATA_RECOVERED_WITHOUT_PARSER_RECONSTRUCTION
ONE_METADATA_CONTRACT_MULTIPLE_VISUAL_LAYOUTS_PROVEN
BROKER_SPECIFIC_RULES_ZERO
VLM_METADATA_REPEATABILITY_MEASURED
SEMANTIC_RELIABILITY=RESIDUAL_LLM_ERRORS_LOCALIZED
FINANCIAL_GENERALIZATION_PRESERVED
```

## Что было проверено

В repository уже существовал нужный owner: `PdfGridExperimentProviderFactory.create_for_openwebui()` принимает PNG region, передаёт native image в Gemini и получает strict structured JSON. Микростенд переиспользовал этот factory-route; новый provider client или framework не создавался.

Для всех cases использован один broker-neutral model view и существующий metadata proposal schema `broker_reports_llm_metadata_proposal_v2`. Contract `1.0.0` и его 11 fact types не менялись. Модель получала только исходный PNG crop, contract и короткую общую instruction. Flattened Canonical text, OCR dump, parser reconstruction и broker hints не передавались.

## Результаты

| Case | Что проверялось | Первый run | Независимые повторы | Квалификация |
|---|---|---:|---:|---|
| B | потерянные parser-ом визуальные пары | 5/5 correct | 3/3 exact | layout восстановлен без reconstruction |
| F | `client code` вне contract | 1 correct, 1 wrong role | 0/3 exact; wrong role 3/3 | residual semantic error модели |
| C | clean control | 3/3 correct | не требовались | control не ухудшен |
| untouched holdout | новая табличная компоновка | 4/4 correct | один frozen exam | пройден без tuning |

Во всех десяти provider submissions: transport failures `0`, contract-invalid results `0`, missed `0`, extra facts `0`, wrong value boundaries `0`, invented values `0`. Единственные ошибки — четыре одинаковых wrong-role решения Case F: одно в initial run и три в repeatability.

Case B дал 3/3 точных независимых повторов после initial success. Это подтверждает основную гипотезу: visual metadata с потерянной пространственной связью не обязательно сначала расплющивать и затем восстанавливать кодом.

Case F дал полезный отрицательный результат. Визуальная модальность не устранила подмену роли идентификатора: проблема локализована в semantic reliability модели, а не в parser/layout.

Untouched holdout был заморожен до ответа: qualified source-page render, manual crop, visual human truth, общий contract и один scheduled run. Результат принят без rerun или изменения стенда: 4/4 correct, ошибок `0`.

## Repeatability и anti-fitting

- single-shot submissions: `10`;
- retries, failover, best-of-N, voting, judge, selection и manual repair: `0`;
- prompt changes между initial, repeatability и holdout: `0`;
- broker-specific hints и regex growth: `0`;
- product activation: `0`.

## Financial и maintained-code regression

`Gate4FinancialCaseRuntimeFactory.create().rebuild_case(...)` сохранил exact frozen equality:

- Holdout A: `39` facts;
- Holdout B: `129` facts;
- source stores unchanged: `true`.

Focused verification: `89 passed`, failures `0`; Ruff: passed. Изменены только изолированный G5.70 proof harness, его tests и safe closeout docs. Financial, Gate 2, metadata product path и runtime source code не менялись.

## Решение и scope stop

Результат соответствует сценарию B: VLM-first adapter является предпочтительным кандидатом для визуальных metadata regions, но semantic reliability остаётся отдельной ограниченной проблемой. Это proof, а не разрешение на подключение к product.

Private crops, source documents/page render, visual truth, exact model inputs, raw outputs и journals сохранены во внешнем evidence bundle и в Git не попадают. Commit, push, PR, automatic region detector, product integration и следующий Goal не выполнялись.
