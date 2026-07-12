# OpenWebUI Broker Reports: Single PDF Whole-Document Gate 2 E2E

Date: 2026-07-12

Final status: `BROKER_REPORTS_SINGLE_PDF_E2E_PARTIAL`.

One approved real broker PDF was processed end-to-end through the production
Gate 1 / Gate 1.5 / Gate 2 path. The run produced a private document-level
extraction packet and safe analytical summary, but complete document-level
coverage was not proven.

## 1. Selected document

Selected source: approved `case_group_002`, `source_ordinal=12`.

Why this document was selected:

- not a toy one-page sample;
- 6 pages with complete usable text layer;
- complete PDF layout coverage;
- 14 high table candidates and 6 line clusters;
- 20 Gate 1 normalized source units;
- normalized table projections available;
- no OCR/VLM/image-only page dependency;
- no hidden parent remainder after deterministic Gate 2 windowing.

Safe preparation counts:

| Metric | Count |
| --- | ---: |
| PDF pages | 6 |
| Usable text-layer pages | 6 |
| Partial/image-only pages | 0 |
| High table candidates | 14 |
| Line clusters | 6 |
| Gate 1 normalized source units | 20 |
| Normalized table projection artifacts | 14 |
| Gate 2 selected source units | 17 |
| Selected normalized table projection units | 6 |
| Selected fallback/full-source units | 11 |

## 2. Execution path

Production path used:

```text
process=false private intake
-> Gate 1 normalization
-> PDF text-layer/layout extraction
-> normalized table projections and fallback source units
-> Gate 1.5 document/issue context
-> Gate 2 input readiness
-> deterministic source-unit segmentation and routing
-> domain-specific Gate 2 packages
-> live broker_reports_gate2_domain_source_fact_pipe
-> strict structured output
-> candidate-binding materialization
-> source-fact validation
-> deterministic stitch
-> private document-level extraction packet
```

Key refs:

| Item | Ref |
| --- | --- |
| Case id | `customer_case_group_002_process_false_gate1_20260712145140` |
| Normalization run | `normrun_99b36819b646dd60` |
| Domain context packet | `art_D_9suS4GUshIzlg5v6s2SWa-HHihjIZH` |
| Document extraction packet | `art_560TBYfqv851r1MN0Gz9JLIrkrFMQ-ES` |

Provider identity:

| Field | Value |
| --- | --- |
| Provider profile | `google_gemini` |
| Model | `models/gemini-3.1-flash-lite` |
| Adapter | `gemini_response_format` |
| Structured output mode | `openwebui_response_format_json_schema` |
| Response format | `json_schema` |
| Repair attempts | `0` |
| Hidden failover | `false` |

## 3. Gate 2 workload

Preflight and partitioning passed.

| Metric | Count |
| --- | ---: |
| Parent selected refs | 2489 |
| Derived accounted refs | 2489 |
| Duplicate parent refs | 0 |
| Unaccounted parent refs | 0 |
| Truncated source units | 0 |
| Pending parent remainders | 0 |
| Bounded windows | 116 |
| Domain packages / expected model calls | 175 |

Package/domain distribution:

| Domain | Packages |
| --- | ---: |
| `document_summary_evidence` | 62 |
| `trade_operation` | 39 |
| `unknown_source_row` | 19 |
| `cash_movement` | 16 |
| `fee_commission` | 16 |
| `income` | 10 |
| `withholding_tax` | 9 |
| `position_snapshot` | 4 |

Execution result:

| Metric | Count |
| --- | ---: |
| Windows executed | 116 / 116 |
| Windows passed all strict checks | 26 |
| Domain packages processed | 175 |
| Domain packages accepted | 55 |
| Domain packages rejected | 120 |
| Raw model calls passed | 124 |
| Raw model calls failed | 51 |
| Source facts persisted | 55 |
| Validated source facts | 55 |
| Stitch results | 116 |
| Validation refs | 175 |

Provider aggregates:

| Metric | Value |
| --- | ---: |
| Provider calls | 175 |
| Provider duration total | 655122 ms |
| Wall-clock runtime | 4209.349 s |
| Input tokens reported | 4584773 |
| Output tokens reported | 79902 |
| Total tokens reported | 4664675 |
| Calls with token usage | 124 |

## 4. Source facts and coverage

Accepted source-fact types:

| Fact type | Count |
| --- | ---: |
| `cash_movement` | 1 |
| `unknown_source_row` | 16 |

Accepted package counts by domain:

| Domain | Accepted packages |
| --- | ---: |
| `trade_operation` | 15 |
| `unknown_source_row` | 14 |
| `document_summary_evidence` | 8 |
| `withholding_tax` | 6 |
| `fee_commission` | 4 |
| `income` | 3 |
| `position_snapshot` | 3 |
| `cash_movement` | 2 |

Coverage buckets:

| Bucket | Count |
| --- | ---: |
| Selected refs | 2489 |
| Typed fact owned refs | 1 |
| Unknown refs | 16 |
| No-fact refs | 297 |
| Conflict refs | 0 |
| Uncovered refs | 2175 |

Issue carry-forward:

- unresolved Gate 1 issue context was carried into Gate 2;
- `issue_fact_links_total=17`;
- skipped/unresolved issue context was not dropped from the packet.

Coverage verdict:

`coverage_matches_preflight=true`, but `coverage_complete=false`.

That means no selected refs disappeared silently from the accounting plan, but
the document was not successfully covered by accepted typed/unknown/no-fact
terminal ownership. Most refs remained uncovered because packages were rejected
or provider calls failed.

## 5. Failure taxonomy

Provider-specific blocker:

- 51/175 raw calls failed;
- all 51 failures were `document_summary_evidence`;
- provider profile was `google_gemini`;
- model was `models/gemini-3.1-flash-lite`;
- schema mode was strict `json_schema`;
- provider failure class was `provider_error_response`;
- provider returned HTTP 400 with message `Request contains an invalid argument.`;
- no tokens or finish reason were reported for failed calls.

Validation blockers:

| Code | Count |
| --- | ---: |
| `source_fact_provenance_missing` | 113 |
| `gate2_model_provider_error` | 51 |
| `candidate_binding_issue_limited_completeness` | 51 |
| `candidate_binding_required_role_missing` | 48 |
| `candidate_binding_required_role_group_missing` | 22 |
| `candidate_binding_semantic_role_forbidden` | 12 |
| `candidate_binding_duplicate_role` | 4 |
| `candidate_binding_fact_field_forbidden` | 4 |
| `candidate_binding_duplicate_fact_field` | 3 |

Qualitative diagnosis:

- Table/source-unit partitioning worked: source refs were deterministically
  windowed without truncation or parent remainder.
- The pipeline understood enough bounded context to persist some typed and
  unknown facts.
- The accepted fact set is too sparse for document-level business use.
- `document_summary_evidence` is currently not reliable on Gemini Flash-Lite
  through the OpenWebUI compatibility path with the strict schema used here.
- Candidate-binding validation is doing its job: it rejected outputs with weak
  provenance, missing roles, or incomplete binding instead of inflating a green
  result.

## 6. Guards and live parity

Runtime guard result:

| Guard | Result |
| --- | --- |
| Ordinary processed upload | not used |
| OpenWebUI Knowledge/RAG | not used |
| Vector delta | zero |
| Document rows delta | zero |
| File rows delta during Gate 2 | zero |
| Knowledge rows delta | zero |
| OCR/VLM | not used |
| Gate 3 / tax / declaration / XLSX | not run |
| OpenWebUI core patch | not used |

Live delivery parity:

| Function | Live SHA |
| --- | --- |
| `broker_reports_gate1_pipe` | `1f45c14e37fd453f16e23672c8c65360ef4b8b5ebb1d7bea63136a06a3aa3d8c` |
| `broker_reports_gate2_source_fact_pipe` | `51bf42f11aa8fca165f77cef8909bf5dcac177cebe9198d68acaa798197ffa58` |
| `broker_reports_gate2_domain_source_fact_pipe` | `21891c42f966cb7383762c5ac2beba73776b41a8b7d1b3258900840d682806e1` |

`live_verify_broker_reports_stage2_delivery.py` passed:

- all function bundles match repository;
- all managed prompts match repository;
- provider profile registry matches;
- repository factory boundary passed.

## 7. Refactor performed

The whole-document run exposed a concrete orchestration defect before the final
run: the PDF was complete, but naive section-level segmentation produced too
many micro-windows.

Changes made:

- added private artifact type
  `broker_reports_document_extraction_packet_v0`;
- refactored Gate 2 source-unit segmentation to group low/medium/mixed
  candidates across section refs within the same parent unit while preserving
  deterministic no-fact and unknown clusters separately;
- added regression coverage for cross-section grouping;
- added a whole-document live e2e runner with bounded windows, resume behavior,
  compact output, extended final snapshot, and document packet persistence;
- did not weaken candidate-binding or source-fact validators;
- did not add broker-specific parsing.

## 8. Verification

Commands run:

```text
python services/broker-reports-gate1-proof/scripts/live_case_group_process_false_gate1_run.py --source-ordinals 12 --cleanup-source-uploads --timeout 900
python services/broker-reports-gate1-proof/scripts/live_update_function_and_passport_prompt.py
python services/broker-reports-gate1-proof/scripts/live_update_gate2_function_and_prompt.py
python services/broker-reports-gate1-proof/scripts/live_update_gate2_domain_function_and_prompts.py
python services/broker-reports-gate1-proof/scripts/live_single_pdf_whole_document_gate2_e2e.py --case-id customer_case_group_002_process_false_gate1_20260712145140 --preflight-only --table-segment-max-refs 40 --text-segment-max-refs 40 --max-model-calls 200 --timeout 900
python services/broker-reports-gate1-proof/scripts/live_single_pdf_whole_document_gate2_e2e.py --case-id customer_case_group_002_process_false_gate1_20260712145140 --table-segment-max-refs 40 --text-segment-max-refs 40 --max-model-calls 200 --timeout 900
python -m pytest services/broker-reports-gate1-proof/tests -q
python services/broker-reports-gate1-proof/scripts/live_verify_broker_reports_stage2_delivery.py
```

Regression result:

```text
219 passed in 26.75s
```

## 9. Final statuses

Proven:

- `BROKER_REPORTS_SINGLE_PDF_E2E_TARGET_READY`
- `BROKER_REPORTS_SINGLE_PDF_GATE1_COMPLETE`
- `BROKER_REPORTS_SINGLE_PDF_TABLE_NORMALIZATION_PASSED`
- `BROKER_REPORTS_SINGLE_PDF_GATE2_PACKAGING_PASSED`
- `BROKER_REPORTS_SINGLE_PDF_AGENTIC_EXTRACTION_COMPLETED`
- `BROKER_REPORTS_SINGLE_PDF_ISSUE_CARRY_FORWARD_PROVEN`
- `BROKER_REPORTS_SINGLE_PDF_ANALYTICAL_REVIEW_READY`
- `BROKER_REPORTS_SINGLE_PDF_VECTOR_GUARD_PASSED`
- `BROKER_REPORTS_SINGLE_PDF_KNOWLEDGE_GUARD_PASSED`

Not proven:

- `BROKER_REPORTS_SINGLE_PDF_SOURCE_FACT_VALIDATION_PASSED`
- `BROKER_REPORTS_SINGLE_PDF_DOCUMENT_COVERAGE_PROVEN`
- `BROKER_REPORTS_SINGLE_PDF_E2E_PASSED`
- `READY_FOR_LIMITED_MULTI_DOCUMENT_CASE_PROOF`

Terminal result:

```text
BROKER_REPORTS_SINGLE_PDF_E2E_PARTIAL
provider blocker: Gemini Flash-Lite strict schema rejects document_summary_evidence
validation blocker: candidate-binding/source-fact provenance gaps
coverage blocker: 2175 / 2489 selected refs remain uncovered
```

## 10. Product verdict

The system can now run one real complete PDF through the full document-level
orchestration path and persist an auditable private packet. That is a meaningful
integration milestone.

It is not yet ready for a limited multi-document proof. The next useful step is
not broader scale; it is a focused fix/proof for the provider/schema behavior
around `document_summary_evidence`, followed by the same single-PDF rerun with
strict validators unchanged.
