# Broker Reports Gate 2 Financial Semantic Packet V6

Status: Goal 4 contract for Candidate Records By Construction.

## Boundary

`Gate2FinancialSemanticV6PacketFactory.create` is the only model-facing V6
packet entrypoint. It accepts only:

- a validated authoritative Evidence Bundle;
- its exact source package;
- the deterministically validated Candidate Compilation;
- the exact Pack/Registry authority.

The packet does not create or repair Typed Options.

## Exact model-visible shape

`broker_reports_gate2_financial_semantic_packet_v6` contains exactly four
ordered blocks:

1. `task`
   - one semantic operation;
   - one concise generic ambiguity rule.
2. `source_context`
   - every source value and exact literal;
   - visible section, row, column, and label context;
   - human-readable authoritative associations.
3. `available_type_cards`
   - the compact, Pack-owned cards for types represented by available options.
4. `typed_options`
   - code-owned option and type IDs;
   - human-readable prebound role/value summaries.

The model selects an existing option ID or the unclassified disposition. It
does not generate a type, role, or source reference.

## Guidance ownership

Generic decision guidance exists once in `task`. Type meanings, distinctions,
examples, counterexamples, and type-specific ambiguity guidance exist only in
`available_type_cards`. Source context and Typed Options contain source data
and prebound records, not a second set of semantic instructions.

## Exclusions

The packet excludes full Pack administration, Skill or Tool identity,
repository paths, provider metadata, internal audit, provenance graphs,
Gate 3 methodology, expected answers, and duplicate instructions.

## Render modes

- `render_financial_semantic_v6_packet_private_exact` renders the exact
  four-block payload for private debugging, including literals and refs.
- `render_financial_semantic_v6_packet_repository_safe` renders only safe
  hashes, counts, type/role IDs, option IDs, and structural summaries.

The repository-safe renderer never emits source literals or source refs.

## Relationship to LLM Semantic Context v1

The
[LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
defines the closed target boundary for a future complete model-visible
request. It requires local aliases, readable evidence-derived hierarchy,
exactly-once authoritative semantic literals, omitted nulls and zero opaque
global IDs across messages and response schema.

The current active four-block V6 packet remains exact and unchanged. It does
not claim conformance with that future target because `source_context` and
`typed_options` intentionally expose exact global source and option IDs under
the current contract.

A later non-active candidate may be constructed only inside
`Gate2FinancialSemanticV6PacketFactory.create` and must preserve this active
payload and hash byte-for-byte. Removing canonical option IDs from the full
model-visible request additionally requires the separate versioned Choice
candidate; it is not part of packet-view refactoring.

## Model-context research

The 2026-07-28
[field-by-field redundancy audit](../../reports/2026-07-28/BROKER_REPORTS_GATE2_SEMANTIC_PACKET_REDUNDANCY_AUDIT.report.md)
inventories every current model-visible field, distinguishes semantic and
structural metadata from code/evidence-only identity, and measures a
conservative Human-readable Slim View across all 10 frozen semantic cases.

The corresponding
[Slim View proposal](../proposals/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_SLIM_VIEW.proposal.md)
is research-only. It keeps exact literals once, projects local readable
structure and aliases, preserves Pack-owned meanings, keeps exact canonical
option IDs and leaves the Choice schema unchanged. Opaque refs, bindings,
provenance, retention and replay remain in existing code-owned authorities.

The proposal is not implemented or active. The current four-block payload,
Prompt, provider request path, Choice, validator/materializer and runtime
behavior remain unchanged. Any implementation must stay inside the existing
packet owner, first produce a non-active zero-call candidate with exact parity
proof, and must not create a second packet builder or alternative Choice
schema.
