# OpenWebUI Broker Reports Gate 2 Bounded Table-Domain Extraction Proof

Date: 2026-07-11

Status: passed for bounded synthetic native/PDF table-domain extraction and bounded real case_group_002 native/PDF table-domain extraction through the existing Gate 2 domain source-fact runtime.

This proof is narrow. It does not authorize whole-corpus extraction, an automatic default runtime switch, Gate 3, tax calculation, declaration generation, XLS/XLSX generation, OCR/VLM, page rendering for extraction, Knowledge/RAG/vector storage, or semantic table-truth claims for PDF.

## Scope proven

The proven route is:

`broker_reports_normalized_table_projection_v0 -> Gate2InputReadinessFactory(prefer_table_projections=True) -> Gate2TablePackageFactory -> Gate2SourceUnitRouterFactory -> Gate2SourceUnitSegmenterFactory -> Gate2DomainSourceFactRuntimeFactory.create -> strict structured-output model boundary -> Gate2SourceFactValidatorFactory -> Gate2SourceFactStitcherFactory -> private broker_reports_source_facts_v0 -> safe compact summary`.

The model receives an already-normalized bounded table row package. It does not reconstruct a table. Table structure remains owned by Gate 1 / normalized table projection.

## Implementation summary

- `source_provenance` now resolves projection-local `table_projection_private_value` paths and validates exact checksums.
- Native and PDF normalized table projections now carry projection-local `private_values`, `source_value_index`, and reproducible value refs.
- `Gate2TablePackageFactory` and `validate_gate2_table_package` enforce strict eligibility: ready projection, high/medium reconstruction quality, complete coverage, zero duplicate/unaccounted refs, and no semantic PDF truth.
- `Gate2InputReadinessFactory(prefer_table_projections=True)` can skip ineligible projection candidates and continue with eligible projections from the same document; documents with no eligible table package remain unpackageable.
- Domain package narrowing now preserves only selected rows/cells/source-value refs/private values and keeps table projection artifact refs, quality metadata, PDF fallback metadata, issue refs, and forbidden assumptions.
- `Gate2DomainSourceFactRuntimeConfig.prefer_table_projections` and the OpenWebUI domain pipe `prefer_table_projections` valve are explicit opt-ins. Default behavior remains unchanged.
- The strict source-fact validator artifact whitelist includes `broker_reports_normalized_table_projection_v0`.

## Selected targets

Synthetic proof:

- Native synthetic CSV: one high-quality normalized table projection, selected one `income` row.
- Synthetic structural PDF: one high-quality normalized PDF table projection, selected one `income` row.

Real case_group_002 proof:

- Native real target: `source_index=12`, `source_container_format=html_text`, projection format `html`.
  - Projection pool: 12 total; 9 eligible; quality counts `high=7`, `medium=2`, `low=3`.
  - Selected package: `source_unit_start=1`, `source_segment_start=1`, high quality.
  - Selected bounded input: 1 row ref, 4 cell refs, 4 source-value refs, derived package size 15,322 bytes.
  - Domain used: `unknown_source_row`.
- PDF real target: `source_index=11`, `source_container_format=pdf`, projection format `pdf`.
  - Projection pool: 14 total; 6 eligible; quality counts `high=6`, `low=3`, `blocked=5`.
  - Selected package: `source_unit_start=0`, `source_segment_start=1`, high quality.
  - Selected bounded input: 1 row ref, 3 cell refs, 3 source-value refs, derived package size 17,527 bytes.
  - Domain used: `unknown_source_row`.

The real proof intentionally used `unknown_source_row` rather than typed income/trade/tax facts. This proves bounded table-projection-to-source-facts execution, validator/stitch coverage, private persistence, and safe fallback behavior without making business or tax claims from real customer rows.

## Proof results

### Synthetic table-domain proof

Command:

```powershell
cd services/broker-reports-gate1-proof
$env:PYTHONPATH='.'
py -3.11 scripts/local_gate2_bounded_table_domain_extraction_proof.py --json
```

Result:

- Overall status: `passed`.
- Native CSV scenario: terminal `completed`; fact type `income=1`; accepted domain packages `1`; rejected `0`; selected refs `1`; uncovered `0`; conflict `0`.
- Structural PDF scenario: terminal `completed`; fact type `income=1`; accepted domain packages `1`; rejected `0`; selected refs `1`; uncovered `0`; conflict `0`.
- Each scenario persisted `broker_reports_source_facts_v0` as `private_case`.
- Each scenario persisted one raw model output as private ArtifactStore payload.
- Strict structured output model boundary was used once per scenario.
- Knowledge/RAG/vector/page rendering/OCR-VLM guards all passed.

### Real native table-domain proof

Command:

```powershell
cd services/broker-reports-gate1-proof
$env:PYTHONPATH='.'
py -3.11 scripts/local_gate2_real_bounded_table_domain_extraction_proof.py --json
```

Native result:

- Scenario: `real_native_html_unknown_source_row`.
- Status: `passed`.
- Runtime terminal status: `completed`.
- Domain package counts: total `1`, accepted `1`, rejected `0`.
- Facts by type: `unknown_source_row=1`.
- Coverage: selected `1`, unknown `1`, no-fact `0`, uncovered `0`, conflict `0`.
- ArtifactStore: table projection records `12`; raw outputs `1`; private source facts `1`; stitch results `1`; Knowledge backend records `0`.
- Validation: source-fact validator passed.
- Issue carry-forward: validator enforced exact package issue policy; no issue refs were dropped or widened.

### Real PDF table-domain proof

Same command as above.

PDF result:

- Scenario: `real_pdf_structural_unknown_source_row`.
- Status: `passed`.
- Runtime terminal status: `completed`.
- Domain package counts: total `1`, accepted `1`, rejected `0`.
- Facts by type: `unknown_source_row=1`.
- Coverage: selected `1`, unknown `1`, no-fact `0`, uncovered `0`, conflict `0`.
- ArtifactStore: table projection records `14`; raw outputs `1`; private source facts `1`; stitch results `1`; Knowledge backend records `0`.
- Validation: source-fact validator passed.
- PDF metadata: structural projection quality/fallback metadata remained bounded to the normalized table projection. No semantic table truth was claimed.

## Real preflight guard evidence

For `source_index=11` PDF preflight:

- Normalization validation: `passed`.
- PDF table candidates found: `14`.
- PDF projections created: `14`.
- Quality counts: `high=6`, `low=3`, `blocked=5`.
- Gate 2 no-model packages built: `6`; blocked candidates `3`.
- Source-value refs total: `1045`; fallback refs total: `228`.
- Duplicate refs: `0`; unaccounted refs: `0`.
- Model calls: `0`; source facts persisted: `0`; Knowledge records: `0`.

This preflight is separate from the real extraction proof above, which selected one high-quality bounded PDF segment and ran it through the domain source-fact runtime.

## Prompt/schema/model audit

- Runtime entrypoint: `Gate2DomainSourceFactRuntimeFactory.create`.
- Runtime opt-in: `prefer_table_projections=True`.
- Real proof wave: `all`, because selected case_group_002 sources are not all in the primary bucket. Scope remained bounded by `source_unit_start`, `source_unit_limit=1`, `source_segment_start`, and `source_segment_limit=1`.
- Domain allowlist: exactly `unknown_source_row` for real proof.
- Synthetic domain allowlist: exactly `income`.
- Model boundary: local strict structured-output client returning `broker_reports_source_facts_v0` under the same validator/stitch runtime path.
- Raw model outputs: private ArtifactStore payloads only.

## Validation and coverage summary

- Table package validator: passed for selected synthetic and real packages.
- Source-fact validator: passed for selected synthetic and real packages.
- Source-value refs: reproduced through resolver-backed source provenance; no foreign value refs accepted.
- Coverage: complete for every selected row; no uncovered refs and no conflicts.
- Header/no-fact rows: covered in the synthetic proof path where applicable; real selected segments were single model-candidate rows, so no no-fact rows were required.
- Issue carry-forward: package issue policy was enforced by the validator; no selected package widened allowed issue refs or forbidden assumptions.
- Failed/ineligible projection candidates were not promoted.

## Guard summary

Passed:

- no ordinary processed upload;
- no Knowledge/RAG;
- no vectorization;
- no OCR/VLM;
- no page rendering for extraction;
- no OpenWebUI core patch;
- no Gate 3;
- no tax calculation;
- no declaration generation;
- no XLS/XLSX generation;
- no PDF semantic table truth claim;
- no raw filenames, private paths, raw rows, raw values, account numbers, personal data, secrets, or env values in this report.

## Verification commands

Focused proof and regression:

```powershell
cd services/broker-reports-gate1-proof
$env:PYTHONPATH='.'
py -3.11 scripts/local_gate2_bounded_table_domain_extraction_proof.py --json
py -3.11 scripts/local_gate2_real_bounded_table_domain_extraction_proof.py --json
py -3.11 -m unittest tests.test_broker_reports_gate2_input_readiness -q
py -3.11 -m unittest tests.test_broker_reports_table_projection tests.test_broker_reports_gate2_domain_extractors tests.test_broker_reports_gate2_source_fact_runtime tests.test_broker_reports_gate2_input_readiness tests.test_broker_reports_gate2_pipe_bundle -q
```

Observed:

- Synthetic proof: `status=passed`.
- Real proof: `status=passed`.
- Readiness regression: 7 tests OK.
- Focused Gate 2/table suite: 62 tests OK.

Full repository service verification:

```powershell
cd services/broker-reports-gate1-proof
$env:PYTHONPATH='.'
py -3.11 -m unittest discover -s tests -q
py -3.11 -m compileall broker_reports_gate1 openwebui_actions scripts -q
git diff --check
```

Observed after final code/test/report updates:

- `unittest discover`: 168 tests OK.
- `compileall`: OK.
- `git diff --check`: no whitespace errors; Windows LF-to-CRLF warnings only.

## Final statuses

- `TABLE_DOMAIN_EXTRACTION_SYNTHETIC_PASSED`
- `NATIVE_TABLE_DOMAIN_EXTRACTION_PASSED`
- `PDF_TABLE_DOMAIN_EXTRACTION_PASSED`
- `TABLE_SOURCE_FACT_VALIDATOR_PASSED`
- `TABLE_ROW_COVERAGE_PROVEN`
- `TABLE_SOURCE_VALUE_REFS_PROVEN`
- `TABLE_ISSUE_CARRY_FORWARD_PROVEN`
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`
- `READY_FOR_LIMITED_TABLE_DOMAIN_EXTRACTION_EXPANSION`

Expansion is safe only under the same constraints: explicit `prefer_table_projections=True`, eligible high/medium complete projections, bounded package/segment limits, strict domain allowlist, private raw outputs, validator/stitch terminal checks, no automatic default runtime switch, and no semantic PDF table-truth or tax/declaration claims.
