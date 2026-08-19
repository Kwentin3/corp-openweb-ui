# G5.61 — LLM Metadata Adapter Generalization Proof

Дата: 2026-08-15
Статус: `CLOSED_NEGATIVE`

## Terminal

```text
LLM_METADATA_ADAPTER_NOT_YET_RELIABLE
EXACT_FAILURE_CLASS_LOCALIZED
FINANCIAL_GENERALIZATION_PRESERVED
```

Один общий LLM metadata adapter реализован и проверен, но не выбран новым primary authority. В единственном frozen run он допустил две ошибки semantic role и пропустил три реально присутствующих metadata assertions. Текущий deterministic G5.60 extractor не заменён, не расширен и не активирован заново.

## Что было заморожено до implementation

- контракт `BROKER_REPORTS_MINIMAL_PERSON_DOCUMENT_METADATA` `1.0.0`, ровно 11 fact types;
- corpus: `pdf_002`, `pdf_024`, `holdout_a`, `holdout_b`;
- одна instruction `1.0.0`;
- один context policy `broker_reports_metadata_context_policy_v1`;
- одна proposal schema `broker_reports_llm_metadata_proposal_v1`;
- один provider/model: `google_gemini` / `models/gemini-3.5-flash`;
- один provider submission на документ, retry `0`, best-of-N `false`, manual repair `false`.

Frozen context projection до coding покрывал все 21 G5.60 oracle facts. Broker-specific prompts, per-document branches, fixed page/column rules, synonym lists и новый human-language regex: `0`.

## Реализованная граница

`Gate3LlmMetadataAdapterFactory` выполняет один путь для всех четырёх документов:

1. читает только Canonical через `ArtifactResolver` и `CanonicalReaderFactory`;
2. строит bounded package из opaque target aliases, region kind и source content;
3. вызывает provider только через `Gate2StructuredModelClientFactory`;
4. принимает модельный JSON только как proposal;
5. deterministic validator восстанавливает Canonical binding и проверяет exact literal, document/version/node/path/source refs, period boundaries и duplicates;
6. ничего не сохраняет в product runtime и не приписывает tax meaning.

Новая persistence, второй runtime owner и product activation отсутствуют. G5.60 остаётся единственным действующим owner этого metadata meaning.

## Frozen run

| Case | Targets / context chars | Model facts | Source-truth correct | Wrong role | Source-present missed |
|---|---:|---:|---:|---:|---:|
| `pdf_002` | 18 / 14,945 | 9 | 9 | 0 | 0 |
| `pdf_024` | 6 / 7,440 | 4 | 3 | 1 | 3 |
| `holdout_a` | 59 / 9,273 | 4 | 3 | 1 | 0 |
| `holdout_b` | 14 / 1,686 | 6 | 6 | 0 | 0 |
| **Total** | **97 / 33,344** | **23** | **21** | **2** | **3** |

Execution accounting:

- provider submissions: `4`, ровно `1` на документ;
- retry / best-of-N / manual output repair: `0 / false / false`;
- model input: `54,921 chars`, `23,080 input tokens`;
- output: `1,509 tokens`;
- provider-reported total: `34,678 tokens`;
- суммарная duration: `53,767 ms`;
- source stores changed: `false`.

Все 23 source literals были реальными exact substrings. Invented literals, invalid physical provenance, duplicates и факты для четырёх заведомо отсутствующих contract fields: `0`. Это не отменяет semantic failure: exact literal сам по себе не доказывает правильную роль.

## Exact failure classes

1. `LLM_METADATA_ROLE_OVERREACH` — два source-backed значения получили неверную contract role: client code был повышен до account identifier; signer/recipient — до report subject party.
2. `UPSTREAM_CANONICAL_METADATA_VALUE_LOSS` — в `pdf_024` Canonical сохранил label lines, но потерял соседние значения периода, клиента и соглашения. Общий adapter не мог доказать отсутствующие в его физическом входе значения.
3. `FROZEN_G5_60_ORACLE_NOT_SOURCE_TRUE` — визуальная сверка обнаружила шесть реальных source facts, отсутствующих в oracle, и три ложных oracle bindings в `pdf_024`.
4. `G5_60_ORACLE_COVERAGE_INCOMPLETE` — три model extras оказались валидными source facts, а не hallucinations: дополнительный depo account, broker identity и owner party.

Machine comparison корректно завершился `semantic_oracle_mismatch`, но его counters `invented/missing` означают только delta к frozen oracle. Source-truth qualification выше имеет приоритет для диагноза и не использовалась для ремонта model output.

## Validator incident

Первичная deterministic validation отклонила timestamp-shaped period boundaries в `holdout_a`: parser принимал date-only, хотя exact Canonical literal содержал time. Исправлен только общий date parser. Те же сохранённые raw model outputs повторно валидированы без provider calls и без изменения output:

```text
provider_calls_during_revalidation = 0
raw_model_output_repaired = false
final_machine_failure = semantic_oracle_mismatch
```

До единственного provider run был также локализован transport-profile preflight failure с `provider_submissions_total=0`; исправлен metadata-specific structured request profile, а не prompt, oracle или output.

## Financial replay

Read-only rebuild через действующую Gate 4 factory/public-query boundary дал:

- `holdout_a`: ровно `39` financial facts;
- `holdout_b`: ровно `129` financial facts;
- canonical JSON equality с frozen G5.58 results: `true` для обоих cases.

Metadata experiment не изменил финансовую extraction/generalization и не писал в source stores.

## Verification

- focused adapter/client/metadata/architecture suite: `85 passed`;
- broad Canonical → Gate 2 → Gate 3 metadata → Gate 4 → architecture/KT1 suite: `178 passed`, `1` unrelated pre-existing deprecation warning;
- generated OpenWebUI bundles regenerated from maintained sources; live deployment не выполнялся;
- private PDFs, values, raw outputs, screenshots, hashes и full oracle остались вне Git.

## KISS и решение

Сохранены один contract, одна instruction, одна schema, один packager, один validator и один factory-routed provider path. Не добавлены broker/layout heuristics, vocabulary growth, retry logic, voting, reconciliation или persistence.

Однако common architecture proof недостаточен для смены authority: две role errors нарушают finish contract. G5.61 закрыт честным отрицательным terminal. Следующий допустимый GOAL — только отдельный `Canonical Metadata Preservation & Oracle Requalification`; новый LLM rerun или activation этим отчётом не разрешены.
