# Broker Reports — V6 qualification Goal 0 authority map

Date: 2026-07-27  
Scope: documentation only  
Base revision: `bbee1f3876f5c959aa4efee8aff2edf00c11026f`

## Acceptance

| Acceptance item | Result |
| --- | --- |
| `QUALIFICATION_AUTHORITIES` | `FULLY_MAPPED` |
| `DUPLICATE_PATHS` | `IDENTIFIED` |
| `NEW_CONTRACTS` | `ZERO` |
| `PROVIDER_CALLS` | `ZERO` |
| Runtime changes | `ZERO` |
| Stage mutations | `ZERO` |

## Normative path

The repository already contains the complete qualification path. The reuse
decision is to repair its seams in place:

```text
V6 Prompt
  -> Gate2OpenWebUIRequestBuilder
  -> Gate2StructuredModelClientFactory
  -> existing OpenAI or Anthropic adapter
  -> provider transport
  -> adapter-owned Gate2ProviderExecutionMetadata
  -> V6 choice schema / execution identity
  -> Gate2FinancialSemanticV6DecisionEvidenceFactory
  -> deterministic expansion, validator and materializer
  -> terminal qualification receipt
```

The product-side V6 Pack, compact projection, Evidence Bundle, Typed Options,
Candidate Compiler, four-block packet, minimal choice, expansion, validator,
materializer, Managed Domain, Domain API, Gate 3 successor, technical
preclose and no-financial-regex invariant are outside this program and remain
unchanged.

## Authority inventory

| Concern | Normative contract and factory | Current caller | Duplicate or defect | Reuse decision |
| --- | --- | --- | --- | --- |
| Prompt loading | `Gate2FinancialSemanticV6QualificationPrompt` and `_prompt` in `gate2_financial_semantic_v6_qualification.py:134-140,700-711`; canonical bytes/version in `gate2_financial_semantic_v6_evidence.py:61-65` | preflight and terminal runner | The Prompt is reconstructed locally and its boundary failed live Nano even though dry parity passed | Keep one exact Prompt object and pass it directly to the existing request builder |
| Canonical request construction | `Gate2OpenWebUIRequestBuilder.build` in `gate2_model_requests.py:49-65`; V6 implementation at `625-696`; factory wiring at `gate2_model_clients.py:76-121` | `Gate2OpenWebUIStructuredModelClient.extract`, `gate2_model_clients.py:152-184` | `financial_semantic_v6_canonical_request`, `gate2_financial_semantic_v6_evidence.py:257-306`, independently rebuilds the same request; preflight compares both at `gate2_financial_semantic_v6_qualification.py:385-405`; runner uses the duplicate only for evidence at `gate2_financial_semantic_v6_qualification_run.py:164-188` | Existing model-request builder is the sole construction authority; evidence may preserve its output, not rebuild it |
| OpenAI adapter | `Gate2ProviderAdapterFactory` and `Gate2OpenAIResponseFormatAdapter`, `gate2_provider_adapters.py:159-199,414-415` | structured model client factory | No second OpenAI adapter in the V6 runner | Reuse directly |
| Anthropic adapter | `Gate2AnthropicNativeMessagesAdapter`, `gate2_provider_adapters.py:423-497` | structured model client factory | No second Anthropic transport in the V6 runner | Reuse directly |
| Response schema projection | `Gate2FinancialSemanticV6ChoiceContractFactory` in `gate2_financial_semantic_v6_choice.py:113-180`; `financial_semantic_v6_response_format` in `gate2_financial_semantic_v6_execution_identity.py:282-300`; provider projection in `gate2_provider_adapters.py:266-285,430-497` | request builder and provider adapter | No V6 runner projection; the duplicate request constructor attaches the same response format | Preserve the choice factory and adapter projections unchanged |
| Usage normalization | Canonical DTO `Gate2ProviderExecutionMetadata`, `gate2_model_contracts.py:29-79`; OpenAI mapping `gate2_provider_adapters.py:310-365`; Anthropic mapping `516-561` | structured model client, then budget and execution identity | Both adapters leave `total_tokens` absent when the provider omits it; V6 execution identity requires it at `gate2_financial_semantic_v6_execution_identity.py:332-358` | Normalize provider fields only in existing adapters; derive optional aggregate from input plus output when both exist |
| Token estimation | `estimate_gate2_request_input_tokens`, `gate2_economy_budget.py:705-720`, called by `Gate2EconomyBudgetSession.prepare_call` at `210-225` | structured model client | V6 local proof also estimates `(request_context_bytes + 3) // 4` at `gate2_financial_semantic_v6_local_proof.py:319-326` | Budget policy remains admission authority; local-proof estimate is diagnostic only and must not decide admission |
| Budget admission and accounting | `Gate2EconomyBudgetSessionFactory` / `Gate2EconomyBudgetSession`, `gate2_economy_budget.py:120-169`; pre-call admission at `170-295`; post-call accounting at `297-430` | structured model client at `gate2_model_clients.py:160-172,238-245` | `finalize_call` rejects actual input above the pre-call estimate ceiling at `357-364`, discarding a response after transport | Retain this single policy path, separate hard pre-call authorization from non-destructive post-call actual accounting |
| Qualification receipts | Exact/private and repository-safe per-decision evidence is owned by `Gate2FinancialSemanticV6DecisionEvidenceFactory.create`, `gate2_financial_semantic_v6_evidence.py:142-253`; terminal aggregation is in `gate2_financial_semantic_v6_qualification_run.py:326-480` | terminal runner | Failure receipts and aggregate quality are produced even when no semantic decision was admitted | Extend the existing receipts with honest terminal class and lifecycle counters; no replacement evidence contract |
| Attempt accounting | terminal runner counters and receipt, `gate2_financial_semantic_v6_qualification_run.py:89-122,452-461` | terminal runner | `provider_calls` increments before `extract` at `172`; receipt hard-codes one attempt at `453`; pre-transport failures therefore consume attempts | Count local invocation, transport submission, response, semantic decision and product admission separately; submission is the attempt boundary |
| Stage Action delivery | qualification-only Action `openwebui_actions/broker_reports_gate2_economy_qualification_action.py:16-19,146-173`; delivery/readback/rollback script `scripts/live_deliver_broker_reports_gate2_economy_qualification_action.py:69-221,396-450` | live delivery script and V6 qualification CLI | No parallel delivery script is needed | Reuse unchanged until an accepted receipt authorizes a later scoped stage update |

## V6 Nano and Haiku defect classification

### Nano

The preserved Nano receipt records ten
`gate2_financial_semantic_v6_prompt_contract_mismatch` failures and no provider
decision. The failure occurred before transport, but the runner incremented
`provider_calls_total` to ten, hard-coded one provider attempt, and emitted
`MODEL_NOT_SAFE_FOR_SHADOW`.

Correct classification: request-builder/harness failure, not model quality.
It consumed zero provider submissions under the new accounting rule.

### Haiku

The preserved Haiku report records ten actual provider submissions and ten
responses, but zero admitted semantic decisions:

- six responses were rejected after transport because actual input usage
  exceeded the pre-call estimated-input target;
- four responses were rejected because Anthropic omitted `total_tokens`,
  although input and output usage were present.

The runner then published zero precision/recall and
`MODEL_NOT_SAFE_FOR_SHADOW`. Those values do not measure model quality because
no semantic decision crossed the technical admission boundary.

Correct classification: six post-response budget-contract defects and four
usage-normalization/metadata defects. These ten provider submissions remain
historical consumed calls, but they do not establish a model-semantic verdict.

## Duplicate paths to remove or demote

1. Remove `financial_semantic_v6_canonical_request` as an independent request
   constructor; capture the exact result of `Gate2OpenWebUIRequestBuilder`.
2. Keep the local-proof byte estimator as diagnostic output only; the economy
   budget session is the only admission authority.
3. Keep provider-specific usage lookup inside the existing adapters; the V6
   runner consumes only `Gate2ProviderExecutionMetadata`.
4. Replace the runner's pre-call `provider_calls += 1` and hard-coded attempt
   count with lifecycle accounting tied to actual transport submission.
5. Publish model-quality metrics only from admitted semantic decisions.

No new schema, factory, adapter, request builder, provider profile, budget
calculator, evidence contract, Action or delivery script is justified.

## Next permitted goal

Goal 1 may repair the Prompt-to-request-builder seam using
`Gate2OpenWebUIRequestBuilder`. Provider calls remain forbidden.
