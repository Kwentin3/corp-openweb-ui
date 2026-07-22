# Broker Reports Workflow Goal 5D — Private Intake Bytes Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5d-private-intake-byte-resolver-v1`

Correction family: native workflow integration

Implementation status: PASSED

Live native-workflow reproof: PENDING AFTER MERGE

## Trigger

Goal 2 live reproof showed that the private-intake receipt, owner, hash, file row and persisted storage object were valid, but Gate 1 reconstructed a generic upload filename that did not exist. The private-intake service deliberately stores a nonce-qualified object name, so the Function published a typed `bytes_unavailable` blocker before rendering or VLM execution.

## Narrow correction

The correction adds one factory-owned resolver for reserved Broker Reports `br-*` sources. It uses the installed OpenWebUI file repository and storage provider, then delegates receipt validation to the installed private-intake contract.

The resolver requires:

- a syntactically valid reserved source identity;
- the authenticated server user;
- an owned persisted file row;
- a valid private-intake receipt whose source identity matches the request;
- a persisted storage path supplied by the trusted row;
- exact byte length and SHA-256 equality with the verified receipt.

Every failure has a stable typed code and fails closed. For a reserved source, client-supplied inline bytes, content and filesystem paths are ignored even when server resolution fails. Generic non-Broker-Reports uploads retain their existing byte path.

Gate 1 asynchronously resolves the trusted private bytes before constructing the normalizer input. The existing FileInput, normalizer, PDF table intake, Gemini semantic runtime, ArtifactStore and Gate 2 handoff remain the only processing path. No alternate parser or test-only processing pipeline was added.

## Preserved boundaries

- private-intake route and receipt schema: unchanged;
- semantic JSON and Gemini prompt: unchanged;
- model/provider selection: unchanged;
- crop detection and rasterization: unchanged;
- WorkloadAuthority and Gate ownership: unchanged;
- ArtifactStore lifecycle and access rules: unchanged;
- native OpenWebUI processing, Knowledge, RAG, embeddings and vectorization: still forbidden;
- local OCR/Paddle: not added.

The new resolver is included in the deterministic Gate 1 closed-world bundle and imports only APIs installed in the OpenWebUI runtime at the host integration boundary.

## Verification

Focused tests prove exact receipt-owned byte return, cross-owner rejection before storage access, hash mismatch rejection, invalid reserved identity rejection, factory routing, and the Pipe rule that forged client inline content/path can neither replace trusted bytes nor rescue a failed receipt.

Terminal local results:

- affected intake, WorkloadAuthority, Gate, bundle, architecture, atomic-release and privacy regression: 98 passed;
- Ruff on changed production and test sources: passed;
- compile check: passed;
- `git diff --check`: passed;
- boundary-aware scan of private control literals across all correction files: zero findings.

Source and bundle SHA-256 identities:

- private-intake byte resolver: `48c648e7a2432dd0d5be9ce02f91c6015bdaf6d5459d2ec85e8e941206d4d08d`;
- Gate 1 Function source: `d9b7b72b5363b15290ce1fcfc2e59a5ac7051c5b3a36c6ee5446f9f8922a86f7`;
- Gate 1 bundle: `d2958115e657e6d225e6d4f426fcd5371d23104b0e783e60ceaad06d49a211ba`;
- unchanged Gate 2 source-fact bundle: `e286c9a8855dfcffff14dbd1d2a28582e7b3dc3258b8e3a1083dfec6f586505d`;
- unchanged Gate 2 domain bundle: `d5f7edc37eb8beebe020fc5b1de07661fe8f4e5b5bcb5348eb1803aab8dd67ef`.

## Acceptance disposition

- SERVER_AUTHORITATIVE_PRIVATE_BYTE_RESOLUTION: IMPLEMENTED
- RECEIPT_OWNER_IDENTITY_HASH_CHECKS: REQUIRED
- CLIENT_PATH_AUTHORITY: ZERO
- CLIENT_INLINE_BYTES_AUTHORITY_FOR_RESERVED_SOURCE: ZERO
- CROSS_OWNER_ACCESS: REJECTED
- GENERIC_UPLOAD_BEHAVIOR: PRESERVED
- SEMANTIC JSON OR VLM PROMPT CHANGE: ZERO
- KNOWLEDGE/RAG/VECTOR USE: ZERO
- PRIVATE CUSTOMER EVIDENCE IN GIT: ZERO

Goal 5D implementation is complete. Goal 2 remains pending for a live private-intake, Gate 1, Gate 2 and answer-chat reproof after merge and atomic release.
