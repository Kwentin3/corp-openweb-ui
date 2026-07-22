# Broker Reports PDF Semantic VLM Table Runtime v1

Status: `MAINTAINED_REPOSITORY_DEFAULT_OFF`

Authority: this contract defines the maintained visual-table model boundary in
Broker Reports Gate 1. It refactors the existing runtime and provider stack; it
does not introduce a second VLM pipeline.

## Reused implementation

The route continues to use the bounded PDF table crop, `PdfTableRasterFactory`,
Gemini and OpenAI native adapters, OpenWebUI credential resolver, provider
profiles, workload authority, artifact lifecycle, Gate 1 pipe, bundle builder,
and atomic release contracts.

`PdfDualVlmRuntimeFactory.create_for_openwebui` remains the sole maintained
runtime entrypoint. `PdfDualVlmFactProviderFactory.create_for_openwebui` remains
the sole provider-construction entrypoint.

## Model-facing contract

The prompt version is
`broker_reports_semantic_table_transcription_prompt_v1`. The response schema is
`broker_reports_semantic_table_transcription_v1` and contains exactly:

```json
{
  "description": "short source-oriented observation",
  "rows": [["visible text", null, "visible text"]]
}
```

No system identity, provider metadata, hashes, indexes, spans, physical grid,
coordinates, bounding boxes, cell identity, canonical state, or financial
interpretation is requested from the model. Labels and values remain literal
strings. Invalid, truncated, malformed, or extra-field output is terminal and
is never repaired or normalized by application code.

## Provider policy

`pdf_semantic_vlm_provider_selection_v1` makes Gemini the master. The default
policy is:

- one Gemini attempt;
- no hidden retry or automatic second Gemini attempt;
- no OpenAI consensus call;
- no provider switch, merge, or semantic repair;
- no mandatory human review at this boundary.

OpenAI construction and invocation require the explicit versioned
`pdf_semantic_vlm_openai_policy_v1` policy. The allowed modes are `disabled`,
`fallback_on_gemini_terminal_failure`, and `diagnostic_control`. A fallback
retains OpenAI provider identity. A diagnostic control result cannot overwrite
a valid Gemini result. Provider agreement has no authority and is not required
for success.

## Application-owned envelope

The runtime records source/page/crop lineage, immutable input hash, provider and
resolved model identity, prompt/schema hashes, attempt and deadline metadata,
usage, terminal state, response hash, and strict boundary validation result.
It publishes neither a physical grid nor a canonical table in this goal.
Deterministic logical materialization, canonical IDs, rectangular padding,
integrity hashes, persistence, and Gate 2 packaging remain application-owned
work in the subsequent contract goals.

## Legacy disposition

`broker_reports_canonical_table_v1` and
`broker_reports_pdf_dual_vlm_decision_v1` remain readable for historical
evidence and existing review receipts. Their validator is isolated in a
read-only compatibility module with no provider execution. They are not the
default model-facing contract and cannot be silently auto-upgraded into the
semantic origin.

Generated OpenWebUI bundles and stage state are intentionally unchanged until
the atomic release goal. The bundle builder already includes every new source
module so the future bundle can be rendered and compiled in a closed world.
