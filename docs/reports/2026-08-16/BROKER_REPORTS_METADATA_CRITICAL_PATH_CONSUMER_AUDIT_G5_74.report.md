# G5.74 — Metadata Critical-Path & Consumer Audit

Дата: 2026-08-16
Статус: **CLOSED — critical routing defect не обнаружен**

## Вывод

Поля metadata из контракта G5.60 не являются источником финансовой или налоговой истины в maintained runtime. Ошибочный, отсутствующий или несовпадающий account, contract, broker, statement period и party name не меняет admission финансовых фактов, grouping, FIFO, расчётные значения или налоговый период.

`ACCOUNT_IDENTIFIER` не является financial authority. Он остаётся supporting evidence. Налоговый период берётся из подтверждённого user intent и trusted declaration definition; case scope — из authenticated `case_id`/`chat_id`; финансовые значения — из Gate 4 facts и их ролей `date`, `quantity`, `unit_price`, `amount`, `asset`, `currency`.

## Карта критичности

Классы: A — calculation-critical; B — scope-critical; C — evidence/completeness; D — descriptive.

| Поле G5.60 | Класс | Реальный consumer | Влияние при wrong/missing |
|---|---:|---|---|
| `PARTY_NAME` / `FULL_NAME` | C | Gate 5 human-gap closure | Только supporting identity evidence; не подтверждает taxpayer identity самостоятельно |
| `PERSON_BIRTH_DATE` | C | Gate 5 human-gap closure | То же |
| `TAXPAYER_TAX_IDENTIFIER` / INN | C | Gate 5 human-gap closure | То же; отдельный real-source example в текущем producer не доказан |
| `PERSON_CITIZENSHIP` | C | Gate 5 human-gap closure | То же; не выводит residency |
| `DOCUMENT_TYPE` | C | Evidence intake / metadata query | Документальная полнота; не admission и не calculation |
| `DOCUMENT_NUMBER` | C | Evidence intake / metadata query | Документальная полнота; не admission и не calculation |
| `DOCUMENT_DATE` | C | Evidence intake / metadata query | Документальная полнота; не дата финансового события |
| `STATEMENT_PERIOD` | C | Evidence intake / metadata query | Supporting document scope; не tax-period authority |
| `BROKER_LEGAL_NAME` / ISSUER | D | Metadata query / отображение provenance | Не участвует в grouping или tax calculation |
| `ACCOUNT_IDENTIFIER` | C | Evidence intake; legacy clarification policy | Supporting account linkage; отсутствие допускается с warning |
| `ACCOUNT_CONTRACT_IDENTIFIER` | C | Evidence intake; legacy clarification policy | Supporting contract linkage; отсутствие допускается с warning |

В G5.60 metadata contract нет полей класса A или B.

## Настоящий critical path

| Решение | Авторитетный input | Metadata authority |
|---|---|---:|
| Document/fact admission | active Canonical + validated FinancialAnnotations | Нет |
| Case binding | authenticated `case_id` или `chat_id` | Нет |
| Financial grouping | financial fact type, asset, currency и source provenance | Нет |
| FIFO | financial dates, quantity, cost/amount facts | Нет |
| Tax period | validated user intent + trusted declaration definition | Нет |
| Taxpayer identity confirmation | authenticated user/case fact | Metadata — только evidence refs |
| Declaration values | assembled Gate 4/5 financial facts and methodology | Нет |

Кодовые границы:

- G5.60 перечисляет 11 допустимых типов в `gate3_metadata_source_facts.py:27`.
- Evidence intake переносит metadata и financial counts раздельно в `gate5_evidence_intake.py:106`.
- Gate 4 case source set строится через `Gate3NdflCaseReadinessFactory` в `gate4_financial_case_cache.py:363`.
- Case scope берётся из trusted context в `gate4_financial_case_materialization.py:317`.
- Financial role normalization ограничена финансовыми ролями в `gate4_financial_case_materialization.py:353`.
- Tax period сверяется с trusted definition в `gate5_declaration_scope_resolution.py:1603` и `:1621`.
- Identity metadata не заменяет `taxpayer_identity_confirmed` в `gate5_human_gap_closure.py:329`.

## Black-box counterfactual

Добавлен узкий proof-test на реальных factory routes и изолированных SQLite stores, без mocks и без product mutation:

`tests/test_g574_metadata_critical_path.py`

Один и тот же финансовый case прогнан в девяти вариантах:

| Сценарий | Metadata mutation реально прочитана | Financial fingerprint | Факты | Расчёты | Tax period |
|---|---:|---|---:|---:|---:|
| correct | Да | `3a74568a...c1927` | 10 | 1 | 2025 |
| wrong account | Да | тот же | 10 | 1 | 2025 |
| missing account | Да | тот же | 10 | 1 | 2025 |
| wrong contract | Да | тот же | 10 | 1 | 2025 |
| wrong broker | Да | тот же | 10 | 1 | 2025 |
| wrong statement period = 2024 | Да | тот же | 10 | 1 | 2025 |
| missing statement period | Да | тот же | 10 | 1 | 2025 |
| two conflicting statement periods | Да | тот же | 10 | 1 | 2025 |
| party name mismatch | Да | тот же | 10 | 1 | 2025 |

Fingerprint включает type counts, source document set, security fact counts, gross income, recognized acquisition cost, FIFO consumed quantities и costs, direct transaction expense и calculation status. Во всех сценариях также неизменны 10 source facts, 9 active demands и итоговый `PREPARATION_INCOMPLETE`: это ожидаемая явная остановка на неподтверждённых identity/residency facts, а не потеря финансовых фактов.

## Legacy passport / eligibility path

Отдельный pre-Gate2 `document_metadata_passport_v0` не является consumer G5.60, но проверен как потенциальный routing risk.

- Maintained OpenWebUI pipe включает criticality refinement по умолчанию: `openwebui_actions/broker_reports_gate1_pipe.py:215`.
- Pipe явно передаёт значение normalizer’у: `openwebui_actions/broker_reports_gate1_pipe.py:653`.
- Missing account/contract и broker/client metadata имеют `blocks_gate2=False`: `criticality.py:228` и `:248`.
- Missing period блокирует только без независимого scope basis; при case tax year и operation dates проходит с warning. Это покрыто contract tests.

Следовательно, low-criticality metadata не может молча выбросить финансовые факты и в legacy admission path при maintained default configuration.

## Проверки

- G5.74 targeted proof: `2 passed in 8.45s`.
- Contract + factory + architecture suite: `162 passed in 65.37s`; один существующий `DeprecationWarning`, failures = 0.
- Ruff: check passed; format check passed.
- Holdout A: 39 → 39, exact frozen hash equality.
- Holdout B: 129 → 129, exact frozen hash equality.
- Financial source stores unchanged: true.

Для 39/129 переиспользован неизменённый safe verifier G5.69, поэтому внутренние `schema_version` и `goal` его result artifact сохраняют G5.69. G5.74 не выдаёт этот файл за новый financial benchmark, а использует его только как regression evidence.

## Изменения и ограничения

- Product/runtime code: **0 изменений**.
- Metadata extraction, VLM, Markdown, prompts, client-code mapping: **0 изменений**.
- Новый identity framework: **0**.
- Добавлен только audit proof-test, этот report и safe receipt.
- Существующее пользовательское dirty-состояние worktree не изменялось и не очищалось.

## Terminal

```text
METADATA_CONSUMER_CRITICALITY_MAPPED
ACCOUNT_IDENTIFIER_NOT_FINANCIAL_AUTHORITY
LOW_CRITICALITY_METADATA_CANNOT_DROP_FINANCIAL_FACTS
FINANCIAL_FACT_ADMISSION_INDEPENDENT_OF_DESCRIPTIVE_METADATA
PERIOD_AND_IDENTITY_CRITICAL_PATH_EXPLICIT
FINANCIAL_GENERALIZATION_PRESERVED
```
