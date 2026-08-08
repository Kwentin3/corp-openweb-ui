# Broker Reports Gate 3 — Real NDFL Product Path G3.C5

Date: 2026-08-07
Status: PASS

## Простое резюме

1. Словарь живёт в одном versioned package
   `broker-reports-financial-labels@1.0.0`. Оператор открывает его в OpenWebUI:
   `Workspace -> Skills -> Broker Reports Financial Labels`. Tool ID
   `broker_reports_financial_label_dictionary` отдаёт exact bytes для машинной
   проверки, а Gate 3 runtime напрямую загружает тот же hash-pinned package
   resource через единственный factory. Модель Tool не вызывает;
   Knowledge/RAG не используется.
2. Gate 2 сохраняет immutable `CanonicalArtifactV1` и возвращает exact manifest
   ref. Он не вызывает Gate 3.
3. Gate 3 запускает workflow ID `broker-reports-ndfl`, только когда запрос
   пришёл через Workspace Model с тем же stable ID.
4. Workflow получает exact canonical ref и доверенный `ArtifactAccessContext`,
   читает документ через `CanonicalReaderFactory` и CAS-активирует именно эту
   validated version.
5. Результат сохраняется отдельным immutable sidecar
   `FinancialAnnotationsV1`, привязанным к exact canonical version.
6. Весь workflow принадлежит одной пользовательской модели `NDFL`, stable ID
   `broker-reports-ndfl`.
7. Связи используют stable IDs: Workspace Model/workflow
   `broker-reports-ndfl`, base Pipe `broker_reports_gate1_pipe`, provider
   profile `google_gemini`, model `models/gemini-3.5-flash`, dictionary
   `broker-reports-financial-labels@1.0.0`, Skill
   `broker-reports-financial-labels`, Tool
   `broker_reports_financial_label_dictionary`.
8. Legacy Gate 1 Action и два legacy Gate 2 Pipe выключены. Base Pipe оставлен
   активным как ACL-restricted internal runtime dependency: OpenWebUI 0.9.6 не
   исполняет custom Workspace Model, если его `base_model_id` удалён из runtime
   model map. Это не второй product preset.
9. Реальный путь через NDFL прошёл полностью на одном ранее разрешённом CSV.

## Финальный product proof

Путь:

```text
User
-> Workspace Model broker-reports-ndfl
-> broker_reports_gate1_pipe
-> Gate 1 normalization
-> validated CanonicalArtifactV1
-> NDFL exact-ref decision and CAS activation
-> six bounded structural chunks
-> broker-reports-financial-labels@1.0.0
-> models/gemini-3.5-flash
-> deterministic merge
-> FinancialAnnotationsV1
```

Safe результаты финального run:

```text
AUTHORIZED_DOCUMENTS=1
SOURCE_BYTES=212844
PROCESS_FALSE=true
CHUNKS=6
VALIDATED_ANNOTATIONS=109
PERSISTED_ANNOTATIONS=109
FINANCIAL_ANNOTATIONS_ARTIFACTS=1
CANONICAL_VERSIONS=1 ACTIVE
GATE2_MUTATION=NONE
KNOWLEDGE_RAG=NONE
GATE4=NOT_STARTED
```

Sparse annotations остаются предложениями модели, прошедшими closed validator;
число 109 не является утверждением о полноте финансовых фактов и не является
налоговым расчётом.

## Exact audit

Exact private audit сохранён вне Git. Он содержит для каждого из шести chunks:

- exact document fragment и projection;
- exact dictionary object и model Markdown;
- exact instruction;
- exact final provider request;
- raw provider response и raw model output;
- validated output;
- merged result и persisted `FinancialAnnotationsV1`;
- canonical artifact до и после Gate 3.

Safe integrity:

```text
AUDIT_ID=g3c5_20260807_222353
EXACT_FILE_BYTES=27436168
EXACT_FILE_SHA256=14b5379aed57b13ad2a2238d0fd739a2eafd2205b0dbcdf41ec3803ac030d442
MANIFEST_SHA256=81d8fa1c352819f4f3400ef13fb598fb9f62051676c249b59cfc7c7b5bf89069
PRIVATE_BYTES_IN_GIT=false
```

Локальная private path намеренно не записана в Git. После proof audit valve
выключен, exact evidence сохранён, а product Gate 3 остался активен.

## Критически найденные расхождения

До финального PASS были найдены и исправлены три реальные интеграционные
ошибки:

1. Inactive same-ID override скрывал base Pipe из runtime model map. NDFL был
   виден в каталоге, но chat endpoint возвращал `Model not found`. Provider
   вызван не был. Base Pipe возвращён как internal ACL-restricted dependency.
2. API proof не создавал server-attested chat context. Добавлен штатный
   OpenWebUI new-chat контракт `parent_id=null`; provider вызван не был.
3. OpenWebUI мутировал submitted `form_data` через `pop`, из-за чего первый
   provider response завершился локальным
   `gate3_labeling_model_input_audit_failed`. Sidecar не был опубликован.
   Structured model client теперь отправляет deep copy, сохраняя sealed
   prepared request immutable для exact audit. Regression-тест воспроизводит
   это поведение.

Эти попытки не скрыты. Финальный six-chunk run — отдельный полный batch без
retry, repair, fallback или provider switching.

## Техническое evidence

Ключевые проверки:

```powershell
python scripts/live_publish_ndfl_workspace_model.py --publish
python scripts/live_ndfl_product_path_proof.py
python -m pytest tests/test_broker_reports_gate3_bounded_labeling.py tests/test_broker_reports_gate2_model_clients.py tests/test_broker_reports_ndfl_product_pipe.py -q
python scripts/build_openwebui_pipe_bundle.py --target all
python -m pytest tests/test_broker_reports_gate_architecture.py::BrokerReportsGateArchitectureTest::test_generated_bundle_modules_match_maintained_source tests/test_broker_reports_gate1_pipe_bundle.py -q
python scripts/live_publish_gate3_financial_label_assets.py
python scripts/live_publish_ndfl_workspace_model.py
python scripts/live_cleanup_gate3_legacy_routes.py
```

Результаты: финальный Gate 3/контракт/architecture suite `133 passed`;
дополнительные historical successor hash-pin проверки `2 passed`; три
read-only live readback завершились `passed` при `provider_calls=0`; финальный
product proof status `passed`.

Machine-readable safe receipt:

- `BROKER_REPORTS_GATE3_REAL_NDFL_PRODUCT_PATH_G3_C5.receipt.safe.json`

## Acceptance

```text
SEMANTIC_CORE=PASS
MANAGED_DICTIONARY_GUI=PASS
DICTIONARY_RUNTIME_BINDING=PASS
GATE2_TO_GATE3_HANDOFF=PASS
EXACT_VERSION_BINDING=PASS
SINGLE_NDFL_USER_ENTRYPOINT=PASS
STABLE_ID_ROUTING=PASS
DUPLICATE_RUNTIME_OWNERS=NONE
REAL_NDFL_PRODUCT_PATH=PASS
GATE2_MUTATION=NONE
GATE3_PRODUCT_STATUS =
CLOSED
```

Gate 4 не начат.
