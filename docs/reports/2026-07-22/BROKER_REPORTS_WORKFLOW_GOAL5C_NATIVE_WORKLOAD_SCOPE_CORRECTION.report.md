# Broker Reports Workflow Goal 5C — Native Workload Scope Correction

Date: 2026-07-22

Branch: `codex/broker-reports-goal5c-native-workload-scope-v1`

Correction family: native workflow integration

Implementation status: PASSED

Live native-workflow reproof: PENDING AFTER MERGE

## Trigger

The Goal 5B live reproof established that the deployed idempotency mechanism received two distinct keys for one native task and source. User, case, chat and source identities were equal, but OpenWebUI supplied no `workspace_model_id` to the first internal Gate 1 invocation and supplied the Gate 1 model identity to the second. The optional invocation field was therefore not a stable workload identity.

## Narrow correction

The Gate 1 Function now maps its workload submission to the stable Function-owned workspace scope `broker_reports_gate1_pipe` before deriving the idempotency key or calling `WorkloadAuthority`.

The authorization and idempotency material still require the server-attested user and case/chat scope plus native source-file identity. The change does not relax `WorkloadAuthority`: exact access checks, unique-key transaction, job-kind check and explicit retry behavior are unchanged. It only prevents OpenWebUI's missing-versus-present model metadata from splitting one Gate 1 workload into two identities.

Artifact authorization remains independent and continues to use the server-injected artifact context. No artifact access rule was weakened.

The key contract remains `broker_reports_gate1_native_request_idempotency_v1`. Keeping the policy identity stable is deliberate: an existing job created when the asserted Gate 1 model identity was present can be reused after this correction instead of forcing a one-time reprocessing. Existing jobs created from the missing-model invocation remain readable but cannot compete with the unique stable key.

## Verification

The integration regression deliberately executes the same chat/source request twice:

1. without workspace-model metadata;
2. with the deployed Gate 1 model identity.

It proves one stable workload scope, one completed job, one completed transition, unchanged artifacts on replay, one domain context packet and a concise nontechnical terminal response. Existing WorkloadAuthority tests continue to prove exact access denial for actual scope substitution and in-place legacy database migration.

Terminal local results:

- affected WorkloadAuthority, Gate 1, bundle, architecture, atomic-release and privacy regression: 75 passed;
- Ruff on changed production and test sources: passed;
- `git diff --check`: passed;
- boundary-aware scan of private control literals against the tracked correction: zero findings.

Bundle and source SHA-256 identities:

- Gate 1 Function source: `284021628098908b1ca5af5eb4f02481cf219eeea5f0f8ce4866d7a46aaab382`;
- Gate 1 bundle: `8acbf2b823e3f5a8811cb8bdaedeb97d1713c19b1acc152a1e3e2d56cea17b21`;
- unchanged Gate 2 source-fact bundle: `e286c9a8855dfcffff14dbd1d2a28582e7b3dc3258b8e3a1083dfec6f586505d`;
- unchanged Gate 2 domain bundle: `d5f7edc37eb8beebe020fc5b1de07661fe8f4e5b5bcb5348eb1803aab8dd67ef`.

## Acceptance disposition

- MISSING_VERSUS_PRESENT_NATIVE_MODEL_CONTEXT: ONE WORKLOAD SCOPE IN LOCAL PROOF
- DUPLICATE_GATE1_JOBS: ZERO IN LOCAL PROOF
- DUPLICATE_DOMAIN_CONTEXT_PACKETS: ZERO IN LOCAL PROOF
- USER_CASE_CHAT_SOURCE_BOUNDARIES: PRESERVED
- ACTUAL_SCOPE_SUBSTITUTION: REJECTED
- ARTIFACT_ACCESS_POLICY: UNCHANGED
- EXPLICIT_RETRY_PATH: PRESERVED
- SEMANTIC JSON OR VLM PROMPT CHANGE: ZERO
- KNOWLEDGE/RAG/VECTOR USE: ZERO
- PRIVATE CUSTOMER EVIDENCE IN GIT: ZERO

Goal 5C implementation is complete. Goal 2 remains pending for the required live native-workflow reproof after merge and atomic release from approved `main`.
