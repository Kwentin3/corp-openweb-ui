# OpenWebUI Broker Reports case_group_002 PDF/HTML Source Policy Rerun V2

Дата: 2026-07-08

## Результат

Срез закрыт как V2 proof для `case_group_002`.

Итог: PDF/HTML больше не выбрасываются в OCR из-за слабого text-layer/profile evidence. Они маршрутизируются в отдельный `source_role_policy_review_required` bucket. Gate 2 handoff остается готовым только по текущему accepted subset из 2 документов; расширения subset на PDF/HTML не было.

Финальные статусы:

- `GATE1_PDF_TEXT_LAYER_POLICY_READY`
- `GATE1_HTML_TABLE_EVIDENCE_READY`
- `GATE1_SOURCE_ROLE_POLICY_READY`
- `CASE_GROUP_002_PDF_HTML_RERUN_V2_READY`
- `CASE_GROUP_002_SUMMARY_COUNTS_READY`
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`
- `READY_FOR_SPECIALIST_DECISION_ON_PDF_HTML_SOURCE_POLICY`
- `CASE_GROUP_002_GATE2_SOURCE_FACT_PROOF_LIMITED_TO_CURRENT_ACCEPTED_SUBSET`

## Что изменено

Backend contract теперь различает:

- text-layer / mixed PDF with text evidence;
- raster/image-only PDF requiring OCR;
- HTML/PDF with table/text evidence but no approved source-role policy;
- methodology/output artifacts;
- duplicates/canonical choice;
- unknown role review.

Новый eligibility status: `source_role_policy_review_required`.

Новый Gate 2 handoff ref bucket: `source_policy_review_refs`.

Safe registry role hints используются только при явной private/customer-approved policy. Для PDF/HTML они не дают auto-accept: live policy была `pdf_html_source_policy=review_required`.

## Live Function

Обновлена live Function: `broker_reports_gate1_pipe`.

Задеплоен bundled Pipe:

- bundle SHA-256: `9a4c9194ad2085e55870a779b695514701b982e4492b5ceb7d49922393224c8f`
- live bundle SHA-256: `9a4c9194ad2085e55870a779b695514701b982e4492b5ceb7d49922393224c8f`
- hash parity: `true`
- live source contains `source_role_policy_review_required`: `true`

## Runtime Policy

Retention:

- mode: `customer_approved_test`
- explicit: `true`
- ttl_seconds: `1209600`

Source policy:

- mode: `customer_approved_private_registry`
- explicit: `true`
- `pdf_html_source_policy`: `review_required`
- `accept_pdf_html_source_roles`: `false`
- safe registry role hints count: `16`

ArtifactStore runtime boundary:

- sqlite store: `/app/backend/data/broker_reports_gate1/artifacts.sqlite3`
- private payload root: `/app/backend/data/broker_reports_gate1/payloads`

## Input Package

Live rerun used retained `process=false` refs from the previous controlled private intake. No new upload was needed.

Safe aggregate package shape:

- total documents: `16`
- formats: `csv=2`, `pdf=8`, `html_text=4`, `xlsx=2`
- role candidates: `operations_table=6`, `source_broker_report=6`, `calculation_template=2`, `dividends_report=2`
- source evidence candidates from safe registry: `14`

No raw filenames, OpenWebUI file ids, private paths, rows or text are included in this report.

## Chat-Visible Report

Chat output was compact Russian text, not primary full JSON:

```text
Нормализация завершена с предупреждениями.
Получено документов: 16

Итог Gate 1:
- Обработано Gate 1: 16
- Принято к Gate 2: 2
- Исключено как не source: 2
- Требуют OCR: 0
- Требуют проверки роли/source-policy: 11
- Дубликаты / canonical choice: 1
- В reduced subset: 2
- Handoff mode: reduced_subset_ready_for_gate2
```

Chat shape checks:

- compact Russian report: `true`
- starts with JSON: `false`
- contains JSON fence: `false`
- private refs not in chat: `true`

## ArtifactStore Evidence

Live case id: `customer_case_group_002_eligibility_gate1_20260708220334`

Persisted records: `81`

Artifact type counts:

- `source_file_ref_v0`: `16`
- `normalization_run_v0`: `1`
- `document_inventory_v0`: `1`
- `technical_readability_profile_v0`: `1`
- `taxonomy_candidates_v0`: `1`
- `normalization_blockers_v0`: `1`
- `document_source_eligibility_v0`: `1`
- `validation_result_v0`: `1`
- `chat_visible_normalization_report_v0`: `1`
- `gate2_handoff_v0`: `1`
- `private_normalized_table_slice_v0`: `44`
- `private_normalized_text_slice_v0`: `12`

Private payload records: `56`.

Validation status: `passed`.

## Eligibility And Handoff

Eligibility status counts:

- `accepted_for_gate2`: `2`
- `source_role_policy_review_required`: `11`
- `duplicate_needs_canonical_choice`: `1`
- `methodology_or_output_artifact`: `2`
- `requires_ocr_before_gate2`: `0`
- `unknown_role_requires_review`: `0`

Handoff refs:

- included document refs: `2`
- source policy review refs: `11`
- pending review refs: `12`
- duplicate review refs: `1`
- OCR required refs: `0`
- excluded document refs: `2`
- private slice refs passed to Gate 2: `2`
- private slice refs only for included docs: `true`
- terminal blockers not in included refs: `true`

Handoff mode: `reduced_subset_ready_for_gate2`.

## No-RAG / Knowledge / Vector Guard

Runtime deltas for the live rerun:

- file rows delta after intake: `0`
- document rows delta after chat: `0`
- knowledge rows delta after chat: `0`
- vector collections delta: `0`
- vector dirs delta: `0`
- vector files delta: `0`
- vector size delta: `0`

ArtifactStore storage backend counts:

- `openwebui_file`: `16`
- `project_artifact_payload`: `56`
- `project_artifact_store`: `8`
- `openwebui_chat`: `1`
- `openwebui_knowledge`: `0`

Safety flags:

- `customer_docs_loaded_to_knowledge=false`
- `source_fact_extraction_performed=false`
- `tax_correctness_claimed=false`
- `declaration_generated=false`
- `xlsx_generated=false`
- `ocr_performed=false`

## Commands Run

Local verification:

```powershell
python -m unittest discover -s services\broker-reports-gate1-proof\tests -v
python -m compileall services\broker-reports-gate1-proof
git diff --check
rg -n "sys\.path|PYTHONPATH|site\.addsitedir|importlib|parents\[" services\broker-reports-gate1-proof\broker_reports_gate1 services\broker-reports-gate1-proof\openwebui_actions
```

Results:

- unittest: `55` tests passed
- compileall: passed
- `git diff --check`: no whitespace errors; only existing CRLF conversion warnings
- closed-world scan: no findings in backend/adapter runtime modules

Live proof:

```powershell
python services\broker-reports-gate1-proof\scripts\live_case_group_eligibility_rerun.py --env-file .env
```

Result: `passed`.

## Decision

Do not proceed to full PDF/HTML Gate 2 source-fact extraction yet.

Allowed next step: Gate 2 source-fact proof limited to the current accepted subset of `2` documents.

Blocked next step: expanding Gate 2 source subset with PDF/HTML documents before a specialist approves the source-role policy decision for the `11` `source_role_policy_review_required` documents.
