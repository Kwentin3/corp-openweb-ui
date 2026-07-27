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
