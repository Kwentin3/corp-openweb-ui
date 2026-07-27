# Broker Reports Gate 2 Financial Semantic V6 Qualification Harness

Status: canonical V6 qualification and bounded-smoke harness. Full
qualification always requires separate explicit authorization.

## Exact workload

The harness prepares one full-scope qualification attempt for exact model
`gpt-5.4-nano-2026-03-17` through provider profile `openai_gpt` and request
profile `financial_semantic_v6_qualification_v1`.

The identity pins the repository revision, Evidence Bundle and Typed Option
contracts, candidate compilation, four-block semantic packet, minimal choice
schema, compact Semantic Pack projection, Prompt, ambiguity rule, provider
schema, frozen benchmark, exact model/provider route, execution-identity
policy and private/safe evidence contracts.

The 12-case benchmark has ten semantic provider-call slots. Repeated-header
and unsupported-source cases terminate in technical preclose and have zero
provider-call slots.

## Goal 11A boundary

`Gate2FinancialSemanticV6QualificationFixtureFactory.create` and
`Gate2FinancialSemanticV6QualificationPreflightFactory.create` are the only
Goal 11A harness routes.

The preflight rebuilds every semantic authority through canonical factories,
proves request-builder/canonical-request parity, obtains bounded in-memory
budget authorizations, and exercises the exact evidence contract with
synthetic zero-token execution captures. It performs no provider call and
does not consume the one attempt.

The qualification-only Action publishes the V6 workload snapshot while all
production admissions remain empty. Its delivery path requires exact
repository/live content readback and proves rollback by restoring the prior
Action and then the candidate.

## Safety

The Goal 11A CLI exposes no execute mode and writes no evidence. Provider
execution, terminal evidence preservation, and product-gate disposition are
reserved for Goal 11B.

## Goal 11B terminal execution

`qualify_financial_semantic_v6` is the only terminal execution and
product-gate boundary. The dedicated Goal 11B CLI has no implicit execution
mode: `--execute-exact-attempt`, a new repository-safe receipt path, and a new
private evidence directory outside the repository are all required.

The runner makes one call for each of the ten semantic cases and no call for
either technical-preclose case. A case failure is recorded and does not cause
a retry, fallback, repair, Prompt mutation, regex routing, or a second
qualification attempt.

Every provider call is checkpointed immediately. Exact canonical request,
returned choice, available execution metadata, and failure evidence remain
private outside Git. The repository-safe receipt contains only synthetic case
IDs, classifications, aggregate quality/cost/latency metrics, hard-gate
counts, and cryptographic links to private evidence.

The terminal product gate is exactly one of `MODEL_SAFE_FOR_SHADOW` and
`MODEL_NOT_SAFE_FOR_SHADOW`. Shadow safety requires all ten hard gates to be
zero, exact typed precision and recall, ten semantic calls, zero technical
calls, zero hidden retries/fallbacks/repairs, exact evidence for every call,
and all canonical product invariants. This qualification does not admit a
production model.

## Bounded two-case smoke

`smoke_financial_semantic_v6` is the only bounded V6 smoke entrypoint. It
selects exactly one frozen unambiguous typed case and one frozen unambiguous
unclassified case from the qualification fixture. The dedicated CLI requires
`--execute-two-case-smoke`, a new repository-safe receipt path and a new
private directory outside Git. It rejects a dirty worktree or consumed path.

The smoke reuses the canonical request builder, model-client/provider-adapter
factory, execution identity, decision evidence, deterministic expansion,
validator/materializer and offline replay. It never executes technical cases,
publishes qualification metrics or admits a production model.

The 2026-07-27 exact Nano run consumed both authorized submissions. The
responses exposed stale execution-identity assumptions about the now-required
OpenAI root-object projection. The existing execution-identity owner was
corrected to compare provider metadata with the exact projection produced by
`Gate2ProviderAdapterFactory.create`, rather than assuming zero transforms and
equal canonical/adapted hashes.

Offline processing of the two exact preserved responses after that correction
passed the full technical path and exact zero-call replay. Both semantic smoke
expectations failed. The result is not a model qualification or model-safety
verdict. The smoke is not accepted, may not be retried under this
authorization, and the full Nano qualification must not run.

## Strong-candidate transparent smoke

A later explicit authorization may select the fixed stronger candidate
`claude-haiku-4-5-20251001` through `anthropic_claude` while retaining the
same two cases and every semantic authority above. The CLI requires an
explicit exact-candidate selector in both zero-call preflight and execute
modes. Execution additionally requires a new safe receipt, a new private
directory outside Git, and a new dated `*.report.md` path under
`docs/reports/`.

`Gate2FinancialSemanticV6TransparentSmokeReportFactory` is a reporting
projection only. For the two allowlisted synthetic cases it renders, in
primary-evidence-first order, the readable packet fields actually used for
the semantic decision, exact returned semantic JSON, normalized Choice,
field-by-field comparison, and a bounded diagnosis. It cannot select cases,
call a provider, parse a response, validate, materialize, replay, or publish a
qualification verdict.

The transparent report is not permitted for actual corpus. Actual-corpus
source context and raw values remain outside Git; repository evidence remains
redacted and hash-linked.
