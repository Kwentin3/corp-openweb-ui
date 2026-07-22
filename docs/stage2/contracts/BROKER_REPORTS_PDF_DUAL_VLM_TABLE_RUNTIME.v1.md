# Broker Reports PDF Dual-VLM Table Runtime v1

Status: `LEGACY_READ_ONLY_EVIDENCE_CONTRACT`

Superseded as the maintained model-facing route by
`BROKER_REPORTS_PDF_SEMANTIC_VLM_TABLE_RUNTIME.v1.md`. This document remains
authoritative only for persisted pre-semantic decisions and immutable review
evidence. It does not authorize new dual-provider geometric extraction.

Authority: this contract defines the maintained Gemini/OpenAI visual-table
proposal boundary in Broker Reports Gate 1. Atomic stage delivery is outside
this contract and remains a later release goal.

## Recovered implementation

The runtime selectively promotes the pre-drift implementation already present
in repository history. There is one provider stack:

- `PdfDualVlmFactProviderFactory.create_for_openwebui` owns dual-provider
  construction;
- `PdfGridExperimentProviderFactory` and `GeminiGridExperimentAdapter` own the
  native Gemini transport;
- `OpenAIResponsesVisionAdapter` owns the native OpenAI Responses transport;
- `Gate2OpenWebUIProviderConnectionResolver` resolves both credentials from
  OpenWebUI provider configuration;
- `dual_vlm_canonical_table_normalizer_v4` and
  `broker_reports_canonical_table_v1` remain the prompt and output contract;
- `PdfDualVlmRuntimeFactory.create_for_openwebui` is the maintained Gate 1
  orchestration entrypoint.

Files under `scripts/` with the historical provider or canonical-contract
module names are import-only compatibility shims. They contain no transport,
prompt, schema, or validator implementation.

## Input boundary

The dual-provider normalizer accepts exactly one
`broker_reports_pdf_table_candidate_v1` envelope per operation. The envelope
contains one declared table crop and its source/PDF/page/crop lineage. The
runtime verifies:

- the candidate schema and manifest hash;
- PDF/source identity, page number, crop identity and source/image bounds;
- renderer identity, 150 DPI, lossless rendering and no silent resize;
- PNG byte count and SHA-256;
- an envelope containing only the manifest and private PNG bytes.

Whole-document bytes are neither accepted nor available to the provider
operation. Page-level table-region detection remains the separate maintained
PDF Table Intake boundary; the paired Gemini/OpenAI extraction path consumes
only its bounded crops.

## Provider selection and execution

`pdf_dual_vlm_provider_selection_v1` is closed:

- execution mode: `dual_provider_comparison`;
- primary: `google_gemini`;
- review provider: `openai_gpt`;
- order: Gemini, then OpenAI;
- one count/preflight and one generation per provider;
- attempt number one with empty lineage;
- no hidden retry, provider failover, provider switch, or third arbiter.

Repository defaults are `models/gemini-3.5-flash` and
`gpt-5.4-mini-2026-03-17`, with a 24,000 counted-input guard, 16,384 output
token limit, and 240-second per-native-request timeout. These identifiers are
configuration, not permanent qualifications. A model change, provider
transport change, prompt/schema change, or expired live receipt requires a new
synthetic live qualification.

Every `broker_reports_pdf_dual_vlm_execution_v1` record preserves source,
page and crop lineage; input hash; provider/profile; requested and resolved
model; prompt id/version/hash; model-view hash; canonical and adapted schema
hashes; schema transform count; input/output limits; timeout and deadline
policy; attempt lineage; token usage; latency; terminal provider state;
response hash; and deterministic validator result. Raw provider responses and
provider text are not part of this record.

## Decision and authority

`broker_reports_pdf_dual_vlm_decision_v1` has only these statuses:

- `proposal_validated_and_accepted`;
- `proposal_requires_review`;
- `proposal_rejected`;
- `malformed_provider_output`;
- `provider_refusal_or_incomplete`;
- `unresolved_visual_scope`;
- `unsupported_visual_layout`.

`pdf_dual_vlm_deterministic_validator_v1` validates provider contracts,
shared bounded input, hashes, policy, attempts and the decision envelope.
Provider confidence, one provider response, or full Gemini/OpenAI agreement
has zero canonical authority.

The current v1 integration deliberately has no source-to-table accounting
producer. Therefore even exact full-provider agreement terminates as
`proposal_requires_review` with `canonical_table=null`. The accepted status is
invalid unless a maintained deterministic source-accounting result is
`passed`, all provider and lineage invariants pass, and canonical promotion is
explicitly enabled by that validator. No current Gate 1 call supplies such a
result. This preserves the research finding that controlled agreement was
strong while real-table agreement was weak and real outputs were not fully
repeatable.

## Current-model qualification

`qualify_pdf_dual_vlm_runtime.py` uses a generated synthetic PDF and one
declared table crop. It retains only safe qualification, request/response
hashes, model identity, schema hashes, token counts, latency, terminal states
and decision identity. It does not retain provider output values or raw
responses.

Live qualification must prove for both configured models:

- exact requested/resolved identity;
- native provider transport through the OpenWebUI credential boundary;
- image input and structured output;
- provider schema projection/compatibility;
- configured input/output limits;
- one-attempt timeout/deadline behavior;
- valid deterministic parsing and output validation.

Deterministic transport tests separately prove refusal, incomplete,
truncation, timeout, malformed JSON, and resolved-model mismatch handling.
Those cases must remain terminal and may not trigger a retry or failover.

## Human reference

The accepted benchmark contour requires
`broker_reports_pdf_dual_vlm_canonical_table_human_reference_v1` plus
`broker_reports_pdf_dual_vlm_canonical_table_human_reference_seal_v1`.
Finalization requires an identified human reviewer, an explicit crop-level
decision for every controlled case, complete cell/span/empty/unreadable
attestations, and confirmation that provider outputs and consensus were not
used as truth. AI reviewer identities are rejected. Reference or seal mutation
invalidates the pair.

The human reference is private evidence. Only schema versions, aggregate
counts, hashes and the compatibility result may enter Git or a safe report.

If the task owner explicitly delegates the visual review to an agent, the
result must use the separate
`pdf_dual_vlm_canonical_delegated_reference_contract_v1`. Its reference and
seal keep `human_reviewed=false`, record the delegation statement only by
SHA-256, identify the reviewer as `delegated_agent`, and retain the same
crop-level attestations and provider-output exclusions. A delegated seal must
never validate as the human-reference schema or be described as human review.

## Gate 1 integration and privacy

The canonical valves are default-off:

- `pdf_dual_vlm_enabled`;
- `pdf_dual_vlm_provider_selection_policy_version`;
- `pdf_dual_vlm_gemini_model_id`;
- `pdf_dual_vlm_openai_model_id`;
- bounded timeout, token and candidate limits.

The route consumes `private_pdf_table_candidates`, persists private proposal
and execution envelopes through the existing Gate 1 artifact lifecycle, and
exposes only aggregate safe metadata. It does not write Knowledge, RAG or
vector state. PaddleOCR, PaddleOCR-VL, Torch and other heavy local OCR
frameworks are absent from the production bundle and server requirements.
