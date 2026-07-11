# OpenWebUI Broker Reports Gate 2 Live Agentic Table Analysis Report

Date: 2026-07-11

Status: real native and PDF single-domain typed verticals passed. Limited
`cash_movement` table expansion is ready under the proven bounds. Full
all-domain synthetic/fan-out expansion is not claimed.

## Scope

```text
broker_reports_normalized_table_projection_v0
-> Gate2InputReadinessFactory(prefer_table_projections=True)
-> Gate2SourceUnitRouterFactory
-> Gate2SourceUnitSegmenterFactory
-> broker_reports_gate2_domain_source_fact_pipe
-> provider-native response_format=json_schema, strict=true
-> Gate2SourceFactValidatorFactory
-> Gate2SourceFactStitcherFactory
```

Out of scope: Gate 3, ledgers, tax, declaration mapping, XLS/XLSX, OCR/VLM,
page rendering, Knowledge/RAG/vector search, whole-document model input,
cross-document consolidation, and semantic PDF table-truth claims.

## Deployed runtime

- Function: `broker_reports_gate2_domain_source_fact_pipe`.
- Runtime path:
  `broker_reports_gate2_domain_source_fact_pipe -> Gate2DomainSourceFactRuntimeFactory.create`.
- Current bundle/live SHA-256:
  `5bf729940993d0496c00df6ff41d235187fa0d899b9eec58327e98ea15aafeed`.
- Managed prompts: 9 active domain prompts.
- Model used for accepted real proofs: `gpt-5.6-sol`.
- Structured output: provider-native `response_format=json_schema`,
  `strict=true`, no fallback.
- Canonical output schema hash:
  `2fcf8ef920e7aceae6fef898d4a4c375db7ab0cd73416bd9e19f76d57bff6da4`.
- `cash_movement` prompt hash:
  `2de111116d1f5ddca9f107459f99b229d4094ad6c4dc0995bd4855502ce5fcbb`.

The live deployment command verified that bundle and live content hashes are
identical and that router/runtime/stitcher factory anchors are present.

## Case and preflight

Case:

```text
customer_case_group_002_process_false_gate1_20260711124118
```

The sources entered OpenWebUI with `process=false`. Gate 1 and preflight
proved:

- readiness: passed;
- packages: 27;
- table candidates: 116;
- eligible targets: 36;
- eligible native/PDF targets: 3/33;
- document rows delta: 0;
- Knowledge rows delta: 0;
- vector delta: 0.

No separate semantic router was required. Both selected verticals had one
selected row, one model candidate, and exactly one typed domain.

## Failure attribution and refactor

The earlier native rejection was caused by a contract gap between table
preparation and exact source-value validation:

- the native row contained separate credit/debit amount columns;
- composite headers were conservatively projected as `unknown`;
- only currency became an exact deterministic candidate;
- the model emitted a date/amount representation the validator could not
  reproduce mechanically.

The refactor did not weaken validation:

- future native projections mechanically recognize bounded composite cash
  headers;
- existing `cash_movement` projections retain every independently
  checksum-reproducible unknown-header decimal as an explicit amount candidate;
- the provider schema permits only exact package candidate values/refs and
  forces fields without candidates to null/empty;
- the LLM selects the business-relevant candidate;
- the finalizer may bind a missing ref only when one exact selected value
  identifies one package candidate;
- the unchanged validator re-resolves the selected source-value ref and
  checksum before acceptance.

Raw output remains private, so the deterministic binding does not erase model
evidence.

## Native real typed proof

Target:

- source format: HTML;
- quality: medium;
- domain: `cash_movement`;
- selected rows/cells/source-value refs: 1/6/6;
- structural headers: `date`, `unknown`, `currency`;
- `semantic_table_truth_claimed=false`.

Run:

```text
sfdrun_cccfd45bf3dbe1b298f13235
```

Result:

- terminal status: `completed`;
- domain packages accepted/rejected: 1/0;
- typed facts: `cash_movement=1`;
- selected/accepted-owned/uncovered/conflict: 1/1/0/0;
- unknown/no-fact: 0/0;
- raw outputs: 1 private strict output;
- fallback outputs: 0;
- private validated source-fact artifacts: 1;
- validation error codes: none;
- complete stitch: 1;
- issue/fact links: 1;
- `ready_for_primary_expansion=true`.

Runtime guard:

- document/file/Knowledge row delta: 0/0/0;
- vector collections/files/bytes delta: 0;
- Knowledge backend records: 0;
- no tax/declaration/XLS/XLSX work.

## PDF real typed proof

Target:

- source format: PDF;
- quality: high;
- domain: `cash_movement`;
- selected rows/cells/source-value refs: 1/3/6;
- structural headers: `unknown`, `amount`, `currency`;
- `semantic_table_truth_claimed=false`.

Run:

```text
sfdrun_3bcfffa3d028c3f4ef1d7292
```

Result:

- terminal status: `completed`;
- domain packages accepted/rejected: 1/0;
- typed facts: `cash_movement=1`;
- selected/accepted-owned/uncovered/conflict: 1/1/0/0;
- unknown/no-fact: 0/0;
- raw outputs: 1 private strict output;
- fallback outputs: 0;
- private validated source-fact artifacts: 1;
- validation error codes: none;
- complete stitch: 1;
- issue/fact links: 1;
- `ready_for_primary_expansion=true`.

Runtime guard:

- document/file/Knowledge row delta: 0/0/0;
- vector collections/files/bytes delta: 0;
- Knowledge backend records: 0;
- no tax/declaration/XLS/XLSX work.

## Synthetic and fan-out boundary

A live all-domain synthetic run on the same bundle used all 9 managed prompts
and produced strict private outputs without fallback. Eight packages were
accepted; `currency_fx` was rejected, leaving one uncovered ref. Therefore:

- `TABLE_DOMAIN_AGENT_SYNTHETIC_LIVE_PASSED` is not claimed;
- `TABLE_AGENTIC_FANOUT_STITCH_PASSED` is not claimed;
- broad all-domain expansion is not authorized.

Subsequent retests encountered a live provider incident:
`gate2_model_provider_error` occurred across `gpt-5.6-sol`,
`gpt-5.4-mini-2026-03-17`, and `gpt-5.6-luna`. Those failed attempts are
retained only as safe diagnostics and are not counted as acceptance evidence.
The final deployed bundle was returned to the exact hash used by both accepted
real verticals.

## Local verification

PowerShell / Python 3.11:

```powershell
cd services/broker-reports-gate1-proof
py -3.11 -m unittest discover -s tests -q
py -3.11 -m compileall broker_reports_gate1 openwebui_actions scripts -q
py -3.11 scripts/build_openwebui_pipe_bundle.py
git diff --check
```

Observed:

- full unittest discovery: 171 tests passed;
- compileall: passed;
- closed-world bundle build: passed;
- bundle/live SHA equality: passed;
- `git diff --check`: passed; Windows line-ending warnings only.

Test isolation used temporary SQLite/payload directories in test setup and
cleanup. The unit under test was not mocked; only network/provider boundaries
were represented by boundary clients. Observable terminal outcomes include
validated private facts, validation artifacts, stitch coverage, and runtime
storage deltas.

Factory parity:

```text
openwebui_actions/broker_reports_gate2_domain_source_fact_pipe.py
-> Gate2DomainSourceFactRuntimeFactory.create
-> Gate2DomainPackageBuilderFactory.create
-> Gate2DomainCandidateFinalizerFactory.create
-> Gate2SourceFactValidatorFactory.create
-> Gate2SourceFactStitcherFactory.create
```

The live proof script calls the same Pipe/runtime route. `FACTORY_REQUIRED`
and `FORBIDDEN` anchors remain present and test-covered.

## Final statuses

Proven:

- `TABLE_LIVE_MANAGED_PROMPTS_READY`
- `TABLE_LIVE_PROVIDER_STRUCTURED_OUTPUT_PASSED`
- `TABLE_DOMAIN_AGENT_RUNTIME_READY`
- `CASE_GROUP_002_NATIVE_REAL_TYPED_FACT_PASSED`
- `CASE_GROUP_002_PDF_REAL_TYPED_FACT_PASSED`
- `TABLE_SOURCE_FACT_VALIDATOR_PASSED`
- `TABLE_ROW_COVERAGE_PROVEN`
- `TABLE_SOURCE_VALUE_REFS_PROVEN`
- `TABLE_ISSUE_CARRY_FORWARD_PROVEN`
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`

Not claimed:

- `TABLE_SEMANTIC_ROUTER_READY` — not required for selected single-domain rows;
- `TABLE_DOMAIN_AGENT_SYNTHETIC_LIVE_PASSED`;
- `TABLE_AGENTIC_FANOUT_STITCH_PASSED`;
- broad all-domain expansion.

Final expansion decision:

```text
READY_FOR_LIMITED_LIVE_TABLE_DOMAIN_EXTRACTION_EXPANSION
```

This status is restricted to the proven topology: one complete table unit, one
selected row window, one deterministic `cash_movement` domain, exact
package-bound value candidates, strict provider schema, private persistence,
terminal validator/stitch checks, and zero Knowledge/RAG/vector/document
writes.
