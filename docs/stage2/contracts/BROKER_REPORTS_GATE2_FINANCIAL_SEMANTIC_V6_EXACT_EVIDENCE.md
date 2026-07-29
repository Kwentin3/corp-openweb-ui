# Broker Reports Gate 2 Financial Semantic V6 Exact Evidence

Status: active V6 evidence current; exact non-active Context V2.0 completeness
packet evidence historical; non-active Context V2.1 candidate/private receipt,
inactive local Choice response profile and provider-neutral sealed request
implemented; GOAL 11 three-provider local projection, materialization,
Financial Domain persistence/restore and exact replay implemented with zero
provider calls; GOAL 12 live Context V2.1 budget-smoke evidence,
failure checkpoint, persistence/restore and exact offline replay implemented
against the frozen pre-call plan, but no GOAL 12 provider submission has run.

## Private evidence

`Gate2FinancialSemanticV6DecisionEvidenceFactory.create` is the active V6
semantic-call evidence boundary. Its additive
`create_context_v2_1_candidate` method is the only GOAL 11 zero-call candidate
evidence boundary. Its additive
`create_context_v2_1_budget_smoke_candidate` and
`create_context_v2_1_budget_smoke_failure` methods are the only GOAL 12
terminal evidence boundaries. The paths share the same owner rather than
introducing a parallel evidence factory. For each active call the owner preserves
privately:

- the exact canonical request and full response-format identity;
- the canonical provider schema hash;
- the normalized minimal semantic choice and its hash;
- the complete deterministic expansion and canonical validated decision;
- the validator and total-materializer result;
- the exact materialized artifact and integrity hashes;
- token, cost and latency metadata through the normalized provider execution
  identity.

Private evidence is returned to the caller. This module has no repository
writer and must never publish raw evidence, source literals or source refs.

## Safe receipt

The repository-safe receipt contains only bounded classifications, counts,
provider metrics and cryptographic hashes. It does not contain the canonical
request, semantic choice, expanded decision, provider response ID, source
literals or source refs.

`private_evidence_hash` is present in the safe receipt and links the two
representations exactly.

## Offline replay

`replay_financial_semantic_v6_decision` accepts the private evidence, its safe
receipt and the same code-owned authorities. It performs:

1. normalized semantic choice;
2. deterministic expansion;
3. canonical validation;
4. total materialization;
5. exact artifact-hash comparison.

Replay performs no provider call, repair, fallback or hidden retry. Any
authority, identity, expansion, validator, artifact or private/safe hash-link
mismatch fails closed.

Persisted private JSON is restored through
`restore_financial_semantic_v6_private_evidence` before replay. The restorer
accepts only the exact private field set, verifies `private_evidence_hash`,
and reinstates canonical contract order after ordinary JSON writers sort
object keys. It does not change values or weaken replay validation.

The additive Context V2.1 path uses
`serialize_financial_semantic_v6_context_v2_1_private_evidence`,
`restore_financial_semantic_v6_context_v2_1_private_evidence` and
`replay_financial_semantic_v6_context_v2_1_decision`. Its private document
preserves the exact final provider request, canonical schema hash,
provider-visible schema, adapter-owned embedded/adapted schema binding,
adapter-extracted output, normalized Choice, Expansion/validation/materialized
hashes, zero-call accounting and replay authorities. The authorities include
the non-active projection identity
`broker_reports_gate2_context_v2_1_local_schema_projection_v1`.

The exact prepared-request authority is not a field-by-field receipt check.
It resolves the repository provider profile, rebuilds the full request through
the canonical request builder and that exact adapter, and requires complete
prepared-contract equality: messages, model, top-level request shape, provider
metadata, full projected schema, wrapper/name/strictness, transform count,
hashes and projection policy. Candidate-only adapter extraction additionally
requires exactly one terminal provider envelope before reading its content.

Context V2.1 replay starts from the restored adapter output, not from the
coordinator's original Python arguments. It receives a freshly reconstructed
validated sealed request, trusted provider profile, adapter identity,
projection policy, exact prepared request and schema from the
sealed-request/projection path. A caller cannot change those private fields,
update their internal authority hashes, reseal the document and pass replay:
the external trusted comparison fails first.

## GOAL 12 live budget-smoke evidence

The GOAL 12 evidence owner is bound to the immutable pre-call plan, exact plan
slot and operation identity. A successful terminal response preserves
privately:

- the exact sealed request, model-visible request, prepared request and final
  provider request;
- the frozen `direct_exact_provider_http_via_openwebui_connection_v1` policy,
  canonical endpoint, exact transport-contract snapshot and its hash;
- the provider-visible schema and all adapter/schema authority hashes;
- the complete raw provider response and independently re-extracted adapter
  output;
- the normalized Choice, frozen expected answer and full mechanical
  field-level diff;
- Expansion, validation and materialized Financial Domain evidence;
- provider execution metadata, budget receipt, token/cost/latency metrics and
  exact one-submission accounting.

An infrastructure, provider or invalid-response failure receives a separate
terminal private checkpoint. It preserves the raw available output, request
authority, exact failure code/class/category and lifecycle accounting. A slot
whose model identity was not proven immutable may only produce
`infrastructure_provider_failure` with zero submissions and zero responses.

The one-shot runner stores private state outside every Git repository and
worktree, HMAC-seals it, and flushes one permanent per-slot `O_EXCL` submission
claim before marking the slot consumed. A git-common execution-owner claim plus
an atomic repository-scoped annotated-tag ref bind the same plan, immutable PR
head and external-directory hash across processes and clones. Resume restores
or byte-validates terminal checkpoints; it never resubmits a claimed or
consumed slot.

`serialize_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence`
and
`restore_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence`
preserve exact ordered private evidence and reject duplicate keys, non-finite
numbers, shape drift and hash-link tampering. The success-only
`replay_financial_semantic_v6_context_v2_1_budget_smoke_decision` rebuilds the
trusted request and adapter authorities, independently extracts the stored raw
response, reruns Choice/Expansion/validation/materialization and requires
exact equality with both private evidence and the safe receipt. Replay records
zero new provider submissions, responses, retries, repairs and fallbacks.
Failure checkpoints are terminal evidence and are deliberately not replayed
as successful semantic decisions.

The repository-safe receipt contains only bounded identity, verdicts, counts,
metrics and hashes. Exact prompts, source values, normalized answers, provider
response IDs and raw transport envelopes remain outside Git. The pre-call
plan is repository-safe; it is not execution evidence and makes no green-suite
or provider-quality claim.

No transport is evidence-eligible until the runner proves the exact head has
an open, non-draft PR and completed-success `broker-reports-ci` check owned by
GitHub Actions, associated with the same pull-request workflow run and exact
job. This provenance is stored in the private execution evidence and reduced
to bounded hashes/identities in repository-safe output.

## Context V2.0 historical packet evidence and current V2.1 boundary

The non-active
[LLM Semantic Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
extends the private-evidence obligation as an exact implemented historical
completeness baseline. Managed Semantic Decision Context GOAL 4 implements the
packet-owned candidate and mapping receipt locally; it does not seal or persist
a complete request. The V2.0 bytes, evidence and receipt remain version-pinned
and unchanged.

The
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
supersedes V2.0 as the current field-eligibility target. GOAL 7 implements the
exact GOAL 5-selected managed projection; GOAL 8 implements only the
non-active PacketFactory V2.1 candidate plus private exact receipt. The later
GOAL 9 adds the separately versioned inactive
[Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md)
profile through the existing Choice authority. GOAL 10 then adds the inactive
provider-neutral request and private sealed-request receipt through additive
`Gate2FinancialSemanticV6ContextLinterFactory.create_context_v2_1`, leaving
historical `create` unchanged. GOAL 11 composes this sealed request with the
existing provider adapters, candidate-only Expansion, materializer, Financial
Domain persistence and transparent projector. It adds no provider call or
runtime activation. The selected Pack `examples[0]`,
`counterexamples[0]`, unique direct rule against the only other current
visible type, and exact first sentence of catalog `meaning` already exist.
GOAL 7 does not author markers or reason wording. The V2.1 Packet candidate,
private mapping receipt, inactive Choice profile and private sealed-request
receipt exist. GOAL 11 evidence is simulated local provider-profile evidence,
not live model execution evidence.

The GOAL 11 proof preserves the exact V2.1 system message, context JSON,
provider-visible response schema, adapter-extracted local answer, packet-owned
private mapping receipt and linter-owned private sealed-request receipt before
normalization. It serializes and restores the candidate private evidence,
parses/restores the preserved V2.1 Choice again, validates the candidate-only
Expansion, materializes the Financial Domain artifact, and reconstructs the
same snapshot after persistence restore. The transparent report records the
evidence/replay hashes without provider access or semantic repair.

The public smoke-report `create_context_v2_1_provider_case` method returns only
a raw closed projection and cannot issue evidence. ProviderProofFactory embeds
that projection in an unissued full proof, independently recomputes the same
unissued proof and requires exact equality. Only then may its private
report-module authority issue an opaque immutable case-evidence token.
Independent canonical full-proof validation follows. The aggregate accepts
only those issued tokens; it never accepts raw or resealed proof dictionaries.
Token projection revalidates its integrity hash, closed field sets, frozen
synthetic cases, governed answers and exact request/output comparison.

The historical live evidence/restorer/replay path remains bound to its active
exact-ID request. Context V2.0 persistence, restore and replay are
`NOT_IMPLEMENTED_NOT_RUN`. Context V2.1 has the separate non-active, zero-call,
synthetic GOAL 11 proof and the frozen but unexecuted GOAL 12 live evidence
path. Neither changes runtime activation nor implies model qualification
before actual terminal GOAL 12 evidence exists.
Private source values, refs, mappings and exact actual-corpus requests remain
outside Git. The Managed Semantic Decision Context GOAL 4 safe receipt contains
only statuses, aggregates, hashes and synthetic-suite accounting.

Current repository-safe GOAL 11 evidence:

- [analytical report](../../reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.report.md);
- [exact synthetic transparent report](../../reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.transparent.json);
- [privacy-safe receipt](../../reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.receipt.safe.json).

Current repository-safe GOAL 12 pre-call evidence:

- [frozen transparent plan](../../reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.precall.transparent.json);
- [privacy-safe plan](../../reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.precall.plan.safe.json).

These files record zero provider submissions. Terminal GOAL 12 result links
must be added only after the exact pre-call commit passes GitHub Actions and
the one-shot runner actually completes.

The packet-owned Managed Semantic Decision Context GOAL 4 proof covers
deterministic candidate bytes,
model-view hash, local-key bijections, necessary reference targets,
field-to-authority pointers, complete exact binding partition and receipt
integrity. It records zero provider calls and no runtime activation. It does
not claim the absent V2.0 Choice profile, any V2.1 implementation,
sealed-request receipt, persistence/restore/replay, provider compatibility or
benchmark admission.

Current repository-safe GOAL 4 evidence:

- [analytical report](../../reports/2026-07-28/BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL4_NON_ACTIVE_CONTEXT_V2.report.md);
- [safe receipt](../../reports/2026-07-28/BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL4_NON_ACTIVE_CONTEXT_V2.receipt.safe.json).

## Goal 2 provider-smoke evidence

The two-case provider smoke checkpoints every returned response immediately.
Its first terminal receipt remains immutable and records the execution-identity
failure seen by the executed revision. Two exact private failure checkpoints
outside Git preserve the canonical request, normalized provider output,
execution metadata and hash links; neither their paths nor raw values are
published.

After the existing execution-identity owner was corrected for adapter `1.1.0`,
an offline-only diagnostic verified both source private hashes and canonical
request/response-format identities, then rebuilt decision evidence through the
same factory and performed exact replay. The diagnostic made zero provider
submissions and did not repair or alter either provider output.

The repository-safe supplemental receipt records only case IDs, boolean
technical/semantic outcomes, counts and cryptographic hashes. It shows exact
technical replay for both responses but failed typed and unclassified smoke
expectations. The evidence therefore does not publish precision, recall,
product admission or a model-safety verdict.

## Transparent synthetic smoke projection

The repository-safe aggregate receipt remains unchanged and continues to
exclude semantic choices and source values. A separate transparent report is
allowed only for the two frozen synthetic smoke cases. Its sole projector is
`Gate2FinancialSemanticV6TransparentSmokeReportFactory`.

For each allowlisted synthetic case the report copies the exact semantic
decision surface from the already-built canonical packet and Choice:

- task instruction;
- source context, including synthetic values;
- all available financial type cards;
- all Typed Options;
- the unclassified disposition and reason codes;
- exact returned semantic JSON;
- normalized semantic Choice;
- explicit expected-versus-actual field comparison;
- technical status and bounded diagnosis.

The projection does not include credentials, provider response IDs, hidden
reasoning, raw provider envelopes, internal filesystem paths, or execution
metadata. It neither changes nor substitutes the exact private evidence and
safe hash link. Actual-corpus values and exact context are never eligible for
this projection.

The 2026-07-27 strong-model smoke evidence is:

- [terminal safe receipt](../../reports/2026-07-27/BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE.receipt.safe.json);
- [immutable interrupted one-case receipt](../../reports/2026-07-27/BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE_INTERRUPTED_AFTER_TYPED.receipt.safe.json);
- [transparent synthetic report](../../reports/2026-07-27/BROKER_REPORTS_GATE2_V6_STRONG_MODEL_TWO_CASE_SMOKE.report.md).

The terminal receipt records exactly two submissions/responses, both case
passes, exact replay, zero hidden retry/fallback/repair and no qualification
attempt. The interrupted receipt proves the first process stopped with one
passed typed case before the continuation submitted only the missing case.

## Nano zero-call forensic

The 2026-07-28
[Nano zero-call forensic](../../reports/2026-07-28/BROKER_REPORTS_GATE2_NANO_ZERO_CALL_FORENSIC.report.md)
uses the already-preserved private checkpoints and published exact replay. It
performs no provider call and changes no execution authority.

For both frozen smoke cases it exposes the repository-safe synthetic semantic
surface, exact Nano answer, normalized answer, field-level expected diff and
the exact Haiku answer on the same workload. A field-level comparison proves
that the Nano and Haiku canonical requests differ only at `$.model`; Prompt,
Semantic Packet and response format are exact matches. The report diagnoses
the typed observation as `OPTION_CONFUSION` and the unclassified observation
as `MODEL_IGNORED_UNCLASSIFIED`, while withholding any general causal or
packet-refinement claim from the two-case sample.

This is documentation over existing evidence. It does not reconstruct a
missing answer, activate a slim packet, change Prompt or Pack meaning, add an
adapter, alter normalization or authorize another provider submission.

## Historical Slim-program GOAL 4 diagnostic evidence

The 2026-07-28 historical Slim-program GOAL 4 execution uses a dedicated
repository-safe synthetic receipt because all six model inputs are projections
of the two frozen non-customer cases. The receipt checkpoints after every call
and contains:

- the sealed exact messages plus complete strict response format;
- exact adapter-extracted semantic output;
- deterministic Local Choice normalization;
- field-level expected diff;
- context-lint and canonical materialization status;
- actual input/output tokens, cost and latency;
- per-call submission/response accounting.

It excludes credentials, provider response IDs, raw provider envelopes,
filesystem paths and hidden reasoning. The receipt is immutable execution
evidence; the report projector may refine a first-pass diagnosis from the same
exact facts but does not rewrite receipt bytes.

Evidence:

- [terminal safe receipt](../../reports/2026-07-28/BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.receipt.safe.json);
- [transparent analytical report](../../reports/2026-07-28/BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.report.md).

The terminal receipt records exactly six submissions/responses, a passed
technical pipeline, failed Haiku unclassified acceptance, zero
fallback/repair/hidden retry, and no full benchmark, qualification verdict,
runtime activation or production admission.
