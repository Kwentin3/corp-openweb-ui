# Broker Reports — Semantic Visual Table Contract Refactoring v1 — GOAL 0

Date: 2026-07-22

Branch: `codex/broker-reports-semantic-goal0-contract-v1`

Scope: contract and architecture migration authority only

Status: `COMPLETED`

## 1. Outcome

The Broker Reports architecture now has one authoritative model-facing visual
table contract:

```text
broker_reports_semantic_table_transcription_v1
```

This is a narrow contract refactoring of the maintained visual-table pipeline,
not a new VLM project. The crop pipeline, provider transports, credential
resolver, ArtifactStore, Gate factories, workload authority, private intake,
review boundary, and release tooling remain in place.

The VLM boundary now owns only:

```json
{
  "description": "short source-oriented description",
  "rows": [
    ["visible text", null, "visible text"]
  ]
}
```

The authority assigns system metadata, logical indexes, null padding,
canonical construction, hashes, persistence, terminal status, and packaging to
deterministic application code. Financial interpretation remains in Gate 2.

GOAL 0 does not switch a provider prompt, execute a provider, materialize a
logical table, implement the semantic validator, qualify a corpus, migrate Gate
2, rebuild deployed bundles, or modify stage.

## 2. Authoritative surfaces

| Surface | Result |
| --- | --- |
| Model-facing schema | `semantic_visual_table_contracts.py` defines the closed `description` + `rows` shape and 120-token description budget |
| Machine policy | `architecture_policy.py` v2 selects the semantic contract, Gemini master policy, optional OpenAI role, zero consensus requirement, zero VLM geometry responsibility, and application-owned envelope |
| Normative contract | `BROKER_REPORTS_SEMANTIC_VISUAL_TABLE_TRANSCRIPTION.v1.md` defines literal transcription, forbidden model fields, deterministic ownership, provider policy, and legacy disposition |
| Global architecture | `BROKER_REPORTS_GATE_ARCHITECTURE.md` is revised to normative policy v2 and keeps financial meaning in Gate 2 |
| Legacy compatibility | `broker_reports_canonical_table_v1` remains readable for historical evidence and immutable artifacts, but is not the new model-facing default |
| Future bundle path | The maintained bundle builder now orders the semantic contract module before `architecture_policy`; generated/deployed bundles are intentionally unchanged in GOAL 0 |

## 3. Acceptance matrix

```text
SEMANTIC_VLM_CONTRACT:
VERSIONED_AND_AUTHORITATIVE

VLM_PHYSICAL_GEOMETRY_RESPONSIBILITY:
ZERO

GEMINI_MASTER_POLICY:
AUTHORITATIVE

OPENAI_MANDATORY_CONSENSUS:
ZERO

MARKDOWN_RUNTIME_DEPENDENCY:
ZERO

LOCAL_OCR_RUNTIME_DEPENDENCY:
ZERO

LEGACY_CONTRACT_DISPOSITION:
EXPLICIT
```

## 4. Anti-drift enforcement

The new architecture test asserts observable contract properties rather than a
snapshot:

- exact root fields are `description` and `rows`;
- the object is closed;
- every cell is string or `null`;
- system identity, provider metadata, indexes, spans, coordinates, physical
  dimensions, cell identity, and `content_state` are absent from the model
  schema;
- Gemini is master and OpenAI is optional control/explicit fallback;
- provider consensus is not required;
- VLM geometry responsibility is zero;
- Markdown parser dependency is forbidden;
- heavy local OCR remains forbidden;
- factory-first provider and deterministic validator/materializer anchors remain
  explicit;
- the legacy contract is imported and proven readable but differs from the new
  model-facing authority;
- the normative documents contain the same decisions.

No provider transport, control-check, UI action, or smoke execution path was
changed. Existing Gate 1 and Gate 2 bundle tests therefore remain the parity
check for those paths; no direct provider bypass was introduced.

## 5. Verification

Shell: Windows PowerShell. No test environment variables were required or set.

Baseline before edits:

```text
python -m pytest -q tests/test_broker_reports_gate_architecture.py
11 passed
```

Final focused and affected-runtime verification:

```text
python -m ruff check <changed Python files>
All checks passed

python -m compileall -q \
  broker_reports_gate1/semantic_visual_table_contracts.py \
  broker_reports_gate1/architecture_policy.py
passed

python -m pytest -q \
  tests/test_broker_reports_semantic_visual_table_contract_authority.py \
  tests/test_broker_reports_gate_architecture.py \
  tests/test_broker_reports_pdf_dual_vlm_canonical_table_contracts.py \
  tests/test_broker_reports_gate1_pipe_bundle.py \
  tests/test_broker_reports_gate2_pipe_bundle.py
35 passed, 5 unrelated SWIG deprecation warnings
```

The future bundle impact was also rendered entirely in memory. Gate 1, Gate 2,
and Gate 2 domain bundle sources all included the new contract module in the
required order and compiled successfully. No generated bundle file was written.

Full service regression:

```text
python -m pytest -q
1043 passed, 20 skipped, 5 unrelated SWIG deprecation warnings in 81.16s
```

The test runner executed all selected tests; it did not abort. The only
intermediate failure was a new documentation-marker assertion that compared
text across Markdown line wraps. Expected continuous phrases were split by
whitespace; the authority content was present. The test was corrected to
normalize whitespace before exact marker comparison. No contract expectation
was weakened.

Test isolation remains the existing per-test module cleanup and temporary
directory setup in bundle tests. There is no handler or irreversible external
boundary in the new contract tests. The relevant irreversible boundary for the
maintained runtime remains persisted/released bundle and stage mutation; GOAL 0
performed neither.

## 6. Privacy and delivery impact

Static inspection of all eight changed/untracked files found:

```text
privacy_violations=0
```

No customer document, crop, provider response, credential, token, absolute user
path, PNG, PDF, or JSON evidence artifact was added. The schema example is
generic.

No `deploy/`, `compose/`, or `openwebui_actions/` file changed. Existing
generated bundles and stage remain aligned with the previously accepted
release. Rebuilding and deploying a semantic runtime before GOALs 1–6 would be
a mixed release and is therefore deferred to GOAL 7.

## 7. Required program status

### GOAL_0_CONTRACT_AUTHORITY: COMPLETED

All GOAL 0 invariants in section 3 are terminally green.

### GOAL_1_GEMINI_MASTER_BOUNDARY: NOT_CLOSED

- Exact unclosed invariant: maintained prompt/provider runtime still uses the
  legacy geometric contract and dual-provider comparison policy.
- Measured evidence: GOAL 0 changed no provider prompt, adapter, runtime, model
  selection, attempt policy, or generated bundle.
- Owning component: maintained Gemini/OpenAI visual-table provider factory and
  runtime.
- Blocker type: required sequential implementation, not an external blocker.
- Narrowest remaining work: connect the existing provider boundary to the new
  schema with one Gemini attempt by default and an explicit versioned OpenAI
  fallback/control policy.

### GOAL_2_DETERMINISTIC_MATERIALIZATION: NOT_CLOSED

- Exact unclosed invariant: no application-owned semantic envelope or
  deterministic rows-to-logical-grid materializer exists yet.
- Measured evidence: GOAL 0 adds only the model response schema and authority.
- Owning component: Gate 1 semantic table materialization boundary.
- Blocker type: scheduled implementation dependency on GOAL 1.
- Narrowest remaining work: build crop-bound envelope creation, maximum-width
  derivation, null padding, indexes, span-1 cells, hashes, and semantic origin.

### GOAL_3_SEMANTIC_VALIDATOR: NOT_CLOSED

- Exact unclosed invariant: strict parsing, description budget enforcement,
  semantic bounds, and terminal validation are not implemented.
- Measured evidence: the current schema declares the shape; it does not parse or
  validate provider responses.
- Owning component: Gate 1 semantic response validator.
- Blocker type: scheduled implementation dependency on GOALs 1–2.
- Narrowest remaining work: implement a bounded no-repair validator and tests
  that distinguish schema validity from literal correctness.

### GOAL_4_THREE_TABLE_HYPOTHESIS: NOT_CLOSED

- Exact unclosed invariant: zero of the required six Gemini semantic executions
  and zero of the required three OpenAI semantic controls have run.
- Measured evidence: frozen crop bytes and prior legacy-schema evidence were not
  touched; legacy runs do not qualify as semantic-contract runs.
- Owning component: private three-table diagnostic runner/evidence pack.
- Blocker type: qualification is sequenced after GOALs 1–3.
- Narrowest remaining work: freeze prompt/schema once, run the exact nine calls
  without retry/merge/repair, and score literal content only.

### GOAL_5_ACTUAL_CORPUS_QUALIFICATION: NOT_CLOSED

- Exact unclosed invariant: semantic-contract actual-corpus fidelity,
  repeatability, fallback frequency, and supported layout profile are unmeasured.
- Measured evidence: no actual-corpus semantic execution occurred in GOAL 0.
- Owning component: maintained bounded actual-corpus qualification contour.
- Blocker type: qualification depends on terminal GOAL 4 evidence.
- Narrowest remaining work: execute the sealed source-only reference contour and
  fail closed any layout outside the accepted fidelity gate.

### GOAL_6_DOWNSTREAM_MIGRATION: NOT_CLOSED

- Exact unclosed invariant: Gate 1/Gate 2 packages do not yet consume the new
  semantic origin/version.
- Measured evidence: legacy artifacts and Gate 2 package code are unchanged.
- Owning component: Gate 1 public handoff and Gate 2 table-package boundary.
- Blocker type: migration depends on the accepted profile from GOAL 5.
- Narrowest remaining work: add an explicit semantic origin path while
  preserving legacy artifact readability and other source families unchanged.

### GOAL_7_ATOMIC_RELEASE: NOT_CLOSED

- Exact unclosed invariant: no atomic semantic runtime release, stage parity
  receipt, valve decision, or rollback proof exists.
- Measured evidence: no generated bundle, stage, deploy, compose, image, loader,
  Knowledge/RAG/vector state, or provider configuration changed.
- Owning component: existing atomic release tooling and stage operator contour.
- Blocker type: release is prohibited until GOALs 0–6 are terminal.
- Narrowest remaining work: rebuild and release the completed contour under one
  versioned valve, prove repository/live parity and rollback, then clean the
  delivery branch/worktree.
