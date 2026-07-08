# OpenWebUI Broker Reports Gate 1 ArtifactStore Persistence And Retention Report

Date: 2026-07-08
Scope: Broker Reports Gate 1 Project ArtifactStore persistence, retention, compact Russian report and Gate 2 resolver.

## 1. Status

- GATE1_ARTIFACTSTORE_PERSISTENCE_READY
- GATE1_COMPACT_RUSSIAN_REPORT_READY
- GATE1_RETENTION_POLICY_READY
- GATE1_PURGE_BEHAVIOR_READY
- GATE1_GATE2_RESOLVER_READY
- GATE1_KNOWLEDGE_GUARD_READY
- GATE1_PRIVACY_CHECKS_PASSED
- GATE1_STORAGE_TESTS_PASSED
- READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE

Operational note: the readiness label is backend/storage-slice readiness on synthetic data. Before live customer-approved files, update the live OpenWebUI Function with the rebuilt bundled Pipe and set an explicit `customer_approved_test` retention policy.

## 2. Implemented

Implemented a project-owned SQLite ArtifactStore slice for `services/broker-reports-gate1-proof`.

Code added:

- `broker_reports_gate1/artifact_models.py`
- `broker_reports_gate1/artifact_lifecycle.py`
- `broker_reports_gate1/artifact_retention.py`
- `broker_reports_gate1/artifact_store.py`
- `broker_reports_gate1/artifact_resolver.py`
- `broker_reports_gate1/gate2_handoff.py`
- `broker_reports_gate1/compact_report.py`
- `tests/test_broker_reports_gate1_artifact_store.py`

Updated:

- `broker_reports_gate1/safe_report.py`
- `broker_reports_gate1/__init__.py`
- `openwebui_actions/broker_reports_gate1_pipe.py`
- `openwebui_actions/broker_reports_gate1_pipe_bundled.py`
- `scripts/build_openwebui_pipe_bundle.py`
- Pipe/bundle tests now assert compact chat output plus technical state through debug/store path.

## 3. Storage Model

Chosen model: hybrid native-first.

OpenWebUI remains native owner for:

- source file upload;
- source file owner/access checks;
- native source file deletion;
- chat/message UX;
- Workspace Model and Pipe entrypoint;
- approved reusable Knowledge only.

Project ArtifactStore owns:

- normalization run records;
- safe internal artifacts;
- private normalized text/table slices;
- validation result;
- Gate 2 handoff refs;
- retention policy;
- expiry and purge status;
- tombstones.

Source bytes are not copied into ArtifactStore by default. Source custody remains OpenWebUI-native; ArtifactStore stores source refs, hash, content type, size and deletion status.

## 4. Persistence And Handoff

Pipe route:

- `openwebui_actions/broker_reports_gate1_pipe.py:97` builds ArtifactStore access context.
- `openwebui_actions/broker_reports_gate1_pipe.py:104` builds retention policy.
- `openwebui_actions/broker_reports_gate1_pipe.py:109` creates the store via `ArtifactStoreFactory`.
- `openwebui_actions/broker_reports_gate1_pipe.py:116` persists the normalizer result.
- `openwebui_actions/broker_reports_gate1_pipe.py:130` returns compact chat output.

Persisted artifacts:

- `normalization_run_v0`;
- `source_file_ref_v0`;
- `document_inventory_v0`;
- `technical_readability_profile_v0`;
- `taxonomy_candidates_v0`;
- `normalization_blockers_v0`;
- `validation_result_v0`;
- `chat_visible_normalization_report_v0`;
- `private_normalized_text_slice_v0`;
- `private_normalized_table_slice_v0`;
- `gate2_handoff_v0`.

Gate 2 handoff is created in `broker_reports_gate1/gate2_handoff.py:31`. Private slices are stored as `private_case` and `project_artifact_payload` at `gate2_handoff.py:115`. Gate 2 handoff refs are built at `gate2_handoff.py:144`.

## 5. Retention And Purge

Implemented retention modes:

- `synthetic_dev`;
- `api_smoke`;
- `customer_approved_test`;
- `production_case`;
- `manual_purge_required`;
- `expires_after_ttl`.

`customer_approved_test` and `production_case` require explicit retention policy. Missing policy fails with `retention_policy_missing`.

Purge behavior:

- `artifact_store.py:216` implements run purge.
- `artifact_store.py:235` marks source file deletion and cascades private-slice purge when policy requires.
- `artifact_store.py:259` purges chat-scoped artifacts when no case policy exists.
- `artifact_store.py:280` purges case artifacts.

After purge, private payload files are deleted and only tombstone records remain. Purged artifact ids cannot be restored.

## 6. Resolver And Access

Resolver:

- `artifact_resolver.py:13` defines `ArtifactResolver`.
- `artifact_resolver.py:17` resolves artifacts through ArtifactStore only.
- wrong user/run/case/chat/workspace fail closed;
- expired refs return `artifact_expired`;
- purged refs return `artifact_purged`;
- privacy-failed refs return `artifact_privacy_failed`;
- source-required reads fail with `source_file_unavailable` when source deletion is observed.

Gate 2 must use ArtifactStore refs. It must not parse chat JSON.

## 7. Compact Russian Report

`compact_report.py:37` renders the primary user-facing message.

The chat output now contains:

- Russian status line;
- files count;
- format summary;
- document class summary;
- warning/blocker summary;
- next step;
- safe technical run ref.

It does not include:

- full JSON block;
- private normalized slices;
- raw filenames;
- raw OpenWebUI file ids;
- local paths;
- rows/cell values;
- account markers.

The old safe JSON remains available as structured data and through ArtifactStore/debug path, not as the default business chat output.

## 8. Knowledge Guard

ArtifactStore rejects `openwebui_knowledge` for private or customer-case artifacts with `knowledge_storage_forbidden`.

Gate 1 safety flags still keep:

```text
customer_docs_loaded_to_knowledge=false
```

No customer docs were used, processed or loaded into Knowledge.

## 9. Test Evidence

Commands run:

```text
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
python -m compileall services/broker-reports-gate1-proof
git diff --check
```

Results:

- unittest: `Ran 45 tests ... OK`;
- compileall: passed;
- `git diff --check`: passed; it emitted only pre-existing CRLF warnings for unrelated files:
  - `deploy/openwebui-static/loader.js`;
  - `services/stage2-stt/tests/test_loader_static.py`.

Additional scans:

- trailing whitespace scan over `services/broker-reports-gate1-proof`: no findings;
- closed-world path/config scan over `services/broker-reports-gate1-proof`: no findings;
- high-confidence secret scan over `services/broker-reports-gate1-proof`: no findings;
- generic secret scan only matched stdlib `secrets` / `token_urlsafe` code used for opaque refs, not secret values;
- `__pycache__` directories created by compile/test were removed.

New test anchors:

- persistence: `tests/test_broker_reports_gate1_artifact_store.py:55`;
- compact report privacy: `tests/test_broker_reports_gate1_artifact_store.py:88`;
- resolver allowed reads: `tests/test_broker_reports_gate1_artifact_store.py:103`;
- resolver denials: `tests/test_broker_reports_gate1_artifact_store.py:117`;
- retention/purge triggers: `tests/test_broker_reports_gate1_artifact_store.py:183`;
- Knowledge guard: `tests/test_broker_reports_gate1_artifact_store.py:214`;
- Gate 2 handoff refs: `tests/test_broker_reports_gate1_artifact_store.py:241`.

## 10. API Smoke

LIVE_API_SMOKE_NOT_EXECUTED

Reason: this slice was completed as backend/storage implementation and test proof. No browser GUI smoke was required, and no live OpenWebUI credentials or customer files were used. The bundled Pipe was rebuilt locally and is ready for a separate live Function update/API smoke if needed.

## 11. Customer-Approved Package Decision

Customer-approved test package can proceed after operational deployment of this storage slice to the target OpenWebUI runtime with an explicit `customer_approved_test` retention policy.

Do not proceed with customer docs if:

- the live Function still runs the previous full-JSON Pipe;
- ArtifactStore path/payload root is not writable in the OpenWebUI runtime;
- retention mode is missing or not explicit for customer-approved mode;
- live API smoke is required by operator policy and has not been run.

No tax correctness, regulatory compliance, declaration generation, XLS/XLSX export, OCR, VLM, source-fact extraction or FNS filing is claimed.
