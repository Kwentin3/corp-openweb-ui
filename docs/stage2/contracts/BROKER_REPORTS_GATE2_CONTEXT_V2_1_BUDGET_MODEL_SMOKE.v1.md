# Broker Reports Gate 2 Context V2.1 Budget Model Smoke v1

Status: `IMPLEMENTED_FROZEN_PRECALL_NOT_EXECUTED`

Date: `2026-07-29`

Scope: qualification-only live smoke for the non-active Context V2.1
candidate. This contract does not activate a runtime route or admit a model to
production.

## 1. Purpose and prerequisite

GOAL 12 begins only after the reviewed, green and merged GOAL 11 local proof.
It compares one budget candidate for OpenAI, Anthropic and Google on the same
four synthetic semantic cases. Provider-specific request projection and
response parsing remain in the existing adapters; semantic expansion,
validation, materialization, evidence and reporting remain in their existing
owners.

The frozen pre-call artifacts are:

- [safe immutable plan](../../reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.precall.plan.safe.json);
- [exact synthetic request projection](../../reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.precall.transparent.json).

Both artifacts have provider calls `0`. Their plan integrity hash is
`9191197bdc947d6ba86db3169ba0d8c911ef88423d611e2c4424a9379167cbab`.

## 2. Frozen candidate ledger

| Provider profile | Frozen model identity | Identity status |
|---|---|---|
| `openai_gpt` | `gpt-5.4-nano-2026-03-17` | dated immutable model ID proven |
| `anthropic_claude` | `claude-haiku-4-5-20251001` | dated immutable model ID proven |
| `google_gemini` | `models/gemini-3.1-flash-lite` | stable selector; dated immutable identity not proven |

The OpenAI and Anthropic candidates use explicit dated IDs. The Google
inventory exposes only stable selectors, not a dated immutable
`gemini-3.1-flash-lite` ID. Therefore the Google candidate must fail closed
before transport unless an immutable identity is independently proven before
its first submission. It must not be silently relabelled or replaced.

Provider identity references:

- [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-nano);
- [Anthropic model IDs and aliases](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions);
- [Google Gemini models](https://ai.google.dev/gemini-api/docs/models).

## 3. Frozen workload and parameters

Provider-major order is fixed. Each provider has these four slots:

1. `syn_successor_v2_unique_cash` — `typed_safe_1`;
2. `syn_successor_v2_no_registry_type` — `no_type_0`;
3. `syn_successor_v2_multiple_compatible` —
   `ambiguous_type_2plus`;
4. `syn_successor_v2_detail_vs_subtotal` —
   `single_type_no_safe_record`.

The full ceiling is `3 × 4 = 12` provider submissions. Every slot has at most
one submission. Model aliases, runtime model overrides, runtime parameter
overrides, retry, semantic repair and fallback are forbidden.

The request profile is
`financial_semantic_v6_context_v2_1_budget_smoke_v1`. The existing economy
policy fixes maximum output tokens at `640`, removes tool/search fields and
applies the repository reasoning policy for the exact candidate. The sealed
request builder also fixes `stream=false`.

The operation identity is derived, not supplied by an operator:

```text
<plan integrity hash>:<slot integrity hash>
```

## 4. Sole execution path

The maintained path is:

```text
frozen V6 fixture and corrected audit
→ Context V2.1 linter
→ sealed-request builder
→ economy-budget admission
→ repository provider adapter
→ Gate2StructuredModelClientFactory
→ exactly one provider boundary
→ adapter terminal extraction
→ Context V2.1 expansion/validation/materialization
→ exact private evidence and offline replay
→ transparent report factory
```

`Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator` is a thin
Qualification-owned coordinator. It does not construct provider payloads,
parse responses, repair semantic output, materialize records or issue report
evidence itself.

The frozen transport policy is
`direct_exact_provider_http_via_openwebui_connection_v1`. OpenWebUI is used
only to resolve the enabled Admin connection and credential. The smoke does
not call OpenWebUI `/api/chat/completions`, filters, system-prompt injection,
RAG or model middleware. The exact direct contracts are:

| Profile | Exact endpoint | Transport contract hash |
|---|---|---|
| `openai_gpt` | `https://api.openai.com/v1/chat/completions` | `307e367f0faa597c22425786486acf1a54d2176bed1c59c800960464d8c12108` |
| `anthropic_claude` | `https://api.anthropic.com/v1/messages` | `0205f7788a1f80ada347848f9ab8c8bb8c6c55aa00e4c44d46a9f8c20f07ca2b` |
| `google_gemini` | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | `f3e99c56e24178d86ae7a75cc8e4dafb73df807fbb715ef76d8f41e8d6b2a6e2` |

Every contract fixes `POST`, timeout `180` seconds, redirects denied, ambient
proxies disabled, response cap `1,048,576` bytes and transport retry `0`.
The configured base URL must be the canonical base byte-for-byte, with at most
one trailing `/`; that single slash is removed before the connection contract
is issued. Whitespace, multiple trailing slashes, case changes, explicit ports
and alternate paths fail closed. The prepared request, transport snapshot and
both hashes are rechecked before a submission.

Before any execute/resume auth, state recovery or transport, the runner holds
one nonblocking OS-backed process lease under repository git-common metadata.
A concurrent process fails closed without touching private state or
checkpoints. Descriptor close releases the transient lease on normal or
exception exit; the operating system releases it on process death, so a later
crash recovery can resume the persistent owner.

Before each allowed transport boundary, the lease-holding runner creates a
permanent per-slot `O_EXCL` submission claim outside Git, flushes it to disk,
and only
then marks the HMAC-sealed private state `consumed_pending_response`. Two
concurrent `--resume` processes therefore cannot submit the same slot. Resume
never resubmits a claimed or consumed slot. A claim without recoverable
terminal evidence is conservatively treated as consumed and becomes
`infrastructure_provider_failure`.

Before the first slot, the runner also creates one exclusive safe execution
claim under the repository git-common metadata. It binds the plan hash,
immutable PR head and a hash of the external private state directory. A second
`--execute`, including one pointed at a different directory, fails before
provider transport; `--resume` accepts only the originally bound directory.
The claim contains no request, response, credential, source value or private
path. A repository-scoped annotated tag
`broker-reports-goal12-execution-lock-<plan_hash>` then claims the same owner
atomically through its ref. Its payload binds the local claim owner, plan,
head and private-directory hash. An unreferenced tag object is not a claim;
the ref creation is the global atomic boundary. The tag must never be deleted.
Crash recovery may create a missing ref only for the exact locally bound
owner. Private state must be outside every Git worktree and is HMAC-sealed;
terminal checkpoints and final outputs are restored or byte-validated, never
blindly overwritten.

## 5. Evidence boundary

Every completed slot has versioned exact private evidence outside Git. It
contains the exact sealed request, prepared request, raw provider response or
failure output, adapter output, normalized answer, execution metadata, budget
receipt and materialization evidence. It also binds the frozen transport
policy, exact transport-contract snapshot and transport-contract hash.

The Git-safe receipt contains only identities, verdicts, counts, metrics and
hash links. Raw provider envelopes, provider response IDs, credentials,
private filesystem paths and hidden reasoning are forbidden in Git.

Offline replay performs provider calls `0` and must reproduce the normalized
answer and materialized artifact exactly for successful slots. Failure
evidence is integrity-restorable but is not semantically replayed as a
successful decision.

## 6. Verdicts and error taxonomy

Each provider/model receives two independent verdicts:

- `TECHNICAL_SMOKE_PASSED` or `TECHNICAL_SMOKE_FAILED`;
- `SEMANTIC_SMOKE_PASSED` or `SEMANTIC_SMOKE_FAILED`.

The closed error categories are:

- `wrong_typed_type`;
- `unsafe_typed`;
- `safe_under_typing`;
- `wrong_unclassified_reason`;
- `invalid_response`;
- `infrastructure_provider_failure`.

A failure for one provider does not stop remaining providers.

## 7. Benchmark admission

A provider/model is eligible for GOAL 13 only when all of these are true:

- the technical pipeline is exact for all four slots;
- all four normalized answers equal the frozen audited answers;
- `unsafe_typed = 0`;
- `invalid_response = 0`;
- retry, repair and fallback totals are `0`;
- immutable model identity is proven.

Eligibility is not production admission. `active=false` and
`production_admissions=[]` remain mandatory.

## 8. Delivery gate

No live submission is allowed until the pre-call plan and harness are committed
on the GOAL 12 branch and the runner verifies an open, non-draft PR for the
exact head. The required real `broker-reports-ci` GitHub Actions check and job
must be completed-success, owned by the `github-actions` app, associated with
that PR, and backed by workflow `Broker Reports CI` at exact path
`.github/workflows/broker-reports-ci.yml` with event `pull_request` and the
same successful run/head. After execution, the exact transparent report,
privacy-safe receipt and canonical documentation are committed to the same
PR. The final immutable head is reviewed again only after its own Actions
check is green.
