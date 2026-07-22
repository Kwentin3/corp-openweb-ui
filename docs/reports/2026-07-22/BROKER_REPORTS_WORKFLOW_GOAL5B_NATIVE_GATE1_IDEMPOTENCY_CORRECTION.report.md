# Broker Reports Workflow Goal 5B — Native Gate 1 Idempotency Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5b-native-gate1-idempotency-v1`

Correction family: native workflow integration

Implementation status: PASSED

Live native-workflow reproof: PENDING AFTER MERGE

## Trigger

Goal 2 native audit executed the deployed private-intake, Action, chat-completion and task paths. Each of two controlled trials created two sequential Gate 1 jobs for one chat and one source scope. Every job completed independently and published a full artifact set, so each trial ended with two domain context packets and 40 newly persisted artifacts. Knowledge, RAG and vector deltas remained zero. Because the workflow produced two equally valid terminal packages, selecting one would have hidden a product integration defect.

## Narrow correction

The correction makes Gate 1 submission idempotent at the maintained `WorkloadAuthority` boundary.

The Gate 1 Function derives a non-reversible key from the trusted user, case, chat and workspace scope plus the sorted native source-file identities. Raw identities and document content are not stored in the key. Requests without a source reference retain the existing non-idempotent behavior.

`WorkloadAuthority.submit` accepts the optional key and performs the lookup and insert inside an immediate SQLite transaction. A repeated request with the same authenticated scope and source returns the existing job. A scope substitution is rejected by the existing authorization boundary, and a job-kind mismatch fails closed. The existing explicit retry route remains separate and does not silently reuse an idempotency key.

An existing workload database is upgraded in place by adding the nullable column and a unique partial index. Legacy rows remain readable. No alternate queue, processing path or test-only pipeline was introduced.

For a reused job, the normal chat response reports one of: already in progress, completed and available for questions, review required, failed, or cancelled. It exposes neither internal JSON nor artifact identifiers.

## Preserved boundaries

The correction does not modify the semantic JSON contract, Gemini prompt, provider selection, crop extraction, private-intake architecture, Gate 1/Gate 2 ownership, ArtifactStore lifecycle, Knowledge/RAG policy, vector policy or OCR policy. All three maintained Function bundles were regenerated deterministically; the Gate 2 version-only rebuild keeps the atomic Function set coherent.

Bundle and source SHA-256 identities:

- WorkloadAuthority source: `47d5f0d3fd83955cdede2605b6c32813d1852080adb3f69d4cb7398ad59db884`;
- Gate 1 Function source: `15d8abe2f224b860e874ba85eb5ddbe305d50e3ab1ccbf09cc780f114f5b481f`;
- Gate 1 bundle: `62e6307feed050dc48e4963b238a06bb40afed7153ff127ed7c8d1d789bf2e91`;
- Gate 2 source-fact bundle: `e286c9a8855dfcffff14dbd1d2a28582e7b3dc3258b8e3a1083dfec6f586505d`;
- Gate 2 domain bundle: `d5f7edc37eb8beebe020fc5b1de07661fe8f4e5b5bcb5348eb1803aab8dd67ef`.

## Verification

Focused proofs establish:

- two submissions through separate authority instances and one shared database resolve to one terminal Gate 1 job and one completed transition;
- an authenticated-scope substitution cannot claim an existing idempotent job;
- an existing database migrates in place and remains operational;
- two Pipe calls for the same native source scope preserve the first artifact count and leave exactly one domain context packet, one workload job and one completed transition;
- the repeated-call response is understandable and contains no technical JSON.

Terminal local results:

- affected WorkloadAuthority, Gate 1, bundle, architecture, atomic-release and privacy regression: 75 passed;
- Ruff on changed production and test sources: passed;
- `git diff --check`: passed;
- boundary-aware scan of the private control literals against the tracked correction diff: zero findings.

## Acceptance disposition

- DUPLICATE_GATE1_JOBS_PER_NATIVE_SOURCE_SCOPE: ONE IN LOCAL PROOF
- DUPLICATE_DOMAIN_CONTEXT_PACKETS: ZERO IN LOCAL PROOF
- REPEATED_REQUEST_REPROCESSING: ZERO IN LOCAL PROOF
- AUTHENTICATED_SCOPE_SUBSTITUTION: REJECTED
- LEGACY_WORKLOAD_DATABASE_READABILITY: PRESERVED
- EXPLICIT_RETRY_PATH: PRESERVED
- TECHNICAL_JSON_IN_NORMAL_CHAT: ZERO
- SEMANTIC JSON OR VLM PROMPT CHANGE: ZERO
- KNOWLEDGE/RAG/VECTOR USE: ZERO
- PRIVATE CUSTOMER EVIDENCE IN GIT: ZERO

Goal 5B implementation is complete. Goal 2 remains pending for the mandated live native-workflow reproof after this correction is merged and atomically released from approved `main`.
