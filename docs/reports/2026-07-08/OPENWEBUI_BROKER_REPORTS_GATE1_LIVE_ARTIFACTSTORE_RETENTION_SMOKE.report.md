# OpenWebUI Broker Reports Gate 1 Live ArtifactStore Retention Smoke Report

Date: 2026-07-08

Scope: live OpenWebUI Broker Reports Gate 1 Pipe Function update and synthetic ArtifactStore/retention/resolver smoke.

Status:

- LIVE_GATE1_ARTIFACTSTORE_PIPE_UPDATED
- LIVE_GATE1_COMPACT_RUSSIAN_REPORT_READY
- LIVE_GATE1_ARTIFACTSTORE_WRITABLE
- LIVE_GATE1_ARTIFACTS_PERSISTED
- LIVE_GATE1_RETENTION_POLICY_APPLIED
- LIVE_GATE1_PURGE_PROVEN
- LIVE_GATE1_GATE2_RESOLVER_PROVEN
- LIVE_GATE1_KNOWLEDGE_GUARD_PROVEN
- LIVE_GATE1_PRIVACY_CHECKS_PASSED
- READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE

## 1. Live Function Updated

Updated live OpenWebUI Function:

```text
broker_reports_gate1_pipe
```

The smoke used the existing Workspace Model wrapper:

```text
workspace_model_id=test
base Pipe Function=broker_reports_gate1_pipe
```

The update was performed through the OpenWebUI Functions API with the current bundled Pipe source:

```text
POST /api/v1/functions/id/broker_reports_gate1_pipe/update
```

No OpenWebUI core patch was applied.
No separate user-facing sidecar UI was created.

## 2. Bundle Version And Source Hash

Deployed bundle:

```text
services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe_bundled.py
```

Live bundle SHA-256 after update:

```text
1b7136d11a1994691f4e9478d39b067077e6d29c599e0fbd4367279a9145c658
```

The live source hash matched the local bundle hash.

The previous live bundle hash before the first update was:

```text
25c62e77dfebb31341570bc6d9806c2d80f3dfb82724e2f664e786191b10e67d
```

Live source checks after update:

- `_BUNDLED_MODULES`: present;
- `ArtifactStoreFactory`: present;
- `ArtifactResolver`: present;
- `live_smoke_trigger_phrases`: present;
- `pipe_backend_normalizer`: present;
- `pipe_stub`: absent.

## 3. Retention Policy

Live synthetic smoke policy:

```text
mode=api_smoke
explicit=True
ttl_seconds=86400
```

The live Pipe also proved that `customer_approved_test` refuses a missing explicit retention policy:

```text
customer_approved_test_missing_policy_refused=true
```

This means the next customer-approved package must set an explicit customer-approved retention policy. The current smoke did not process customer documents.

## 4. Synthetic Inputs

Synthetic inputs used:

- count: `2`;
- one synthetic broker-report text fixture from the canonical Gate 1 normalization testdata set;
- one synthetic operations-table CSV fixture from the canonical Gate 1 normalization testdata set.

Exact raw source filenames are intentionally not printed in this report.

No customer documents were used.

## 5. Chat-Visible Compact Russian Report

The live Workspace Model returned compact Russian text, not full JSON.

Safe excerpt, with the technical run id redacted:

```text
Нормализация завершена.
Обработано файлов: 2

Форматы:
- CSV: 1
- TXT: 1

Найденные типы документов:
- Таблицы операций: 1
- Брокерские отчеты: 1

Следующий шаг:
Можно переходить к извлечению фактов из брокерских отчетов.

Техническая ссылка: run normrun_...

Проверка ArtifactStore:
- хранилище доступно для записи: да
- retention policy: mode=api_smoke, explicit=True, ttl_seconds=86400
- private slices в chat: нет
- private slices в Knowledge: нет
- customer_docs_loaded_to_knowledge=false
- Gate 2 handoff использует opaque refs, не chat JSON
- resolver same-context: allow
- resolver denies wrong-user/wrong-case/expired/purged: ok
- purge удалил private payloads и оставил tombstones
- source facts/tax/declaration/xlsx/ocr flags=false
```

Validation facts:

- `compact_russian_report=true`;
- `full_json_primary_output=false`;
- required live proof markers found: `22`;
- forbidden marker hits: `0`;
- OpenWebUI file id leaks: `0`;
- mojibake/replacement-char check: passed.

## 6. Persisted Artifacts

The live ArtifactStore smoke proved these artifact types were persisted:

- `normalization_run_v0`;
- `document_inventory_v0`;
- `technical_readability_profile_v0`;
- `taxonomy_candidates_v0`;
- `normalization_blockers_v0`;
- `validation_result_v0`;
- `chat_visible_normalization_report_v0`;
- `private_normalized_text_slice_v0`;
- `private_normalized_table_slice_v0`;
- `gate2_handoff_v0`;
- `source_file_ref_v0`.

Private slice payloads were stored through the project ArtifactStore payload backend, not inline in chat output.

## 7. Runtime ArtifactStore Boundary

Runtime boundary configured in the live bundle:

```text
artifact_store_path=/app/backend/data/broker_reports_gate1/artifacts.sqlite3
artifact_payload_root=/app/backend/data/broker_reports_gate1/payloads
```

The live smoke proved this boundary is writable by the OpenWebUI Function runtime.

## 8. Chat And Knowledge Privacy Proof

Chat privacy proof:

- full JSON was not the primary output;
- private slice collection internals were absent from chat;
- raw uploaded file ids were absent from chat;
- raw source filenames were absent from chat;
- synthetic account/source row markers were absent from chat;
- raw text/table slice fields were absent from chat.

Knowledge guard proof:

- ArtifactStore records used no `openwebui_knowledge` storage backend for private slices;
- `customer_docs_loaded_to_knowledge=false`;
- OpenWebUI Knowledge API count before smoke: `0`;
- OpenWebUI Knowledge API count after smoke: `0`;
- Knowledge count unchanged: `true`.

## 9. Gate 2 Resolver Proof

The live smoke proved:

- Gate 2 handoff uses opaque ArtifactStore refs, not chat JSON;
- same-user/same-context resolver access is allowed;
- wrong-user resolver access is denied;
- wrong-case resolver access is denied;
- expired refs are denied;
- purged refs are denied.

No opaque artifact ids are printed in this report.

## 10. Expiry, Purge And Tombstones

The live smoke created a short-retention synthetic probe run inside the same live ArtifactStore boundary.

Proven behavior:

- expiry state causes resolver denial;
- purge deletes private payload files;
- purge leaves allowed tombstone records;
- purged refs cannot be resolved as active payloads.

No private payload content is printed in this report.

## 11. Commands Executed

Local verification:

```text
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
python -m compileall -q services/broker-reports-gate1-proof
python services/broker-reports-gate1-proof/scripts/build_openwebui_pipe_bundle.py
python -m py_compile services/broker-reports-gate1-proof/scripts/live_artifactstore_retention_smoke.py
git diff --check -- services/broker-reports-gate1-proof
```

Live smoke:

```text
python services/broker-reports-gate1-proof/scripts/live_artifactstore_retention_smoke.py --env-file .env
```

Observed results:

- Gate 1 unit tests: `46 tests ... OK`;
- compileall: passed;
- bundle SHA-256: `1b7136d11a1994691f4e9478d39b067077e6d29c599e0fbd4367279a9145c658`;
- live smoke status: `passed`;
- uploaded synthetic files deleted after smoke: `2`.

## 12. Forbidden Work Not Performed

The live smoke preserved the forbidden Gate 1 boundaries:

- `source_fact_extraction_performed=false`;
- `tax_correctness_claimed=false`;
- `declaration_generated=false`;
- `xlsx_generated=false`;
- `ocr_performed=false`;
- no customer documents used;
- no customer documents loaded to Knowledge;
- no private slices loaded to Knowledge.

## 13. Customer-Approved Test Package Readiness

Result:

```text
READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE
```

Reason: the live Function now runs the ArtifactStore-enabled bundled Pipe, returns compact Russian output, persists safe/private artifacts, applies explicit retention, proves resolver checks, proves purge/tombstones and preserves Knowledge/privacy guards on synthetic files.

Before actual customer-approved documents are used, the operator must set the explicit `customer_approved_test` retention policy for that package. Missing explicit policy is already proven to fail closed.
