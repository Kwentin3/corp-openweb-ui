# Broker Reports Gate 2 Financial Semantic Packet V6

Status: `ACTIVE_V6_UNCHANGED_CONTEXT_V2_1_CANDIDATE_NON_ACTIVE`

## Boundary

`Gate2FinancialSemanticV6PacketFactory.create` is the only model-facing V6
packet entrypoint. It accepts only:

- a validated authoritative Evidence Bundle;
- its exact source package;
- the deterministically validated Candidate Compilation;
- the exact Pack/Registry authority.

The packet does not create or repair Typed Options. The same factory also
returns the historical non-active Slim sidecars and the sole current
non-active
[Context V2.1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md)
candidate/private mapping receipt; none is part of `packet.payload`.
Context V2.0 remains explicit version-pinned historical evidence and is not
built on the current per-request path.

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
- `render_financial_semantic_v6_context_v2_candidate_private_exact` renders
  the exact current non-active V2.1 model view for private proof.
- `render_financial_semantic_v6_context_v2_mapping_receipt_private_exact`
  renders its exact V2.1 private mapping receipt.

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

The GOAL 1/2 non-active candidate is constructed inside
`Gate2FinancialSemanticV6PacketFactory.create`. Tests pin all 10 frozen active
payload hashes and UTF-8 byte counts, proving the active payload and hash
remain byte-identical.

The factory additionally returns:

- `Gate2FinancialSemanticV6SlimViewCandidate`, always `active=False`;
- `Gate2FinancialSemanticV6SlimAliasReceipt`, private and integrity-bound to
  both the active packet hash and Slim View hash.

Current request construction continues to read only `packet.payload`. The
private exact active renderer is unchanged; separate private renderers expose
the candidate and receipt for local proof. The repository-safe renderer emits
only their hashes, counts, byte size, inactive status and zero-call accounting.

GOAL 2 advances the candidate to Slim View v2. Choice records contain only
local aliases, local type aliases and readable bindings; canonical
`return_id` is removed. Exact alias-to-option mapping remains private. The
separate versioned
[Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md)
normalizes the response back to the unchanged current Choice.

An optional code-only `slim_choice_order` permutation changes only the
non-active visible choice order and its request-bound alias mapping. Duplicate,
missing or unknown option IDs fail closed. The active packet payload/hash and
canonical compilation order do not change.

## Model-context research

The 2026-07-28
[field-by-field redundancy audit](../../reports/2026-07-28/BROKER_REPORTS_GATE2_SEMANTIC_PACKET_REDUNDANCY_AUDIT.report.md)
inventories every current model-visible field, distinguishes semantic and
structural metadata from code/evidence-only identity, and measures a
conservative Human-readable Slim View across all 10 frozen semantic cases.

The corresponding
[Slim View proposal](../proposals/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_SLIM_VIEW.proposal.md)
is the design-and-evidence companion for the non-active implementation. It
keeps exact literals once, projects local readable structure and aliases,
preserves Pack-owned meanings and leaves the active Choice schema unchanged.
Opaque refs, canonical option IDs, bindings, provenance, retention and replay
remain in existing code-owned authorities.

The proposal is implemented as a non-active zero-call transition candidate.
The current four-block payload, Prompt, provider request path, Choice,
validator/materializer and runtime behavior remain unchanged. The
implementation stays inside the existing packet owner and creates no second
packet builder or second active/canonical Choice schema. The one non-active
Local Choice candidate remains owned by the existing Choice factory.

Across the 10 frozen semantic cases, current payload bytes remain 73,970 and
Slim View v2 bytes are 18,098. The complete current model-visible projection
is 89,220 bytes versus 26,404 with Slim v2 and Local Choice. The corresponding
repository estimator is 22,950 versus 7,247. These are deterministic local
measurements, not provider tokens or semantic-quality evidence.

## Managed Semantic Decision Context GOAL 2 alias audit

The later
[alias necessity and readability audit](../../reports/2026-07-28/BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL2_ALIAS_NECESSITY_AND_READABILITY_AUDIT.report.md)
inspects the non-active candidate without changing this packet owner or either
payload.

Across the frozen semantic suite it finds:

- 45 value aliases, of which 22 have no inbound reference;
- 20 structural aliases, of which 14 have no inbound reference;
- 12 numeric type aliases and 12 positional choice aliases whose
  cross-reference function is necessary but whose spelling is not readable;
- 59 binding strings: 24 duplicate occurrences, 23 unique semantic
  role/value relations and 12 unique readable evidence-eligibility
  predicates.

The implemented non-active Context V2.0 completeness baseline inside this
same factory renders a reference only when another visible field consumes it.
It pairs deterministic keys with
evidence-owned value labels, readable evidence-derived structure and
Pack-owned type titles. The active type-card projection still drops the Pack
title; Context V2.0 uses the versioned extension of that same projection
authority rather than bypassing it from packet code.

The implemented packet sidecar emits a unique local response key and the
mapped type's exact Pack title as a separate label; evidence differences stay
in readable relationships, and `A/B` is not the sole presentation. This is
exact historical V2.0 evidence, not the current V2.1 response profile. The
separately versioned
[Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md)
binds its strict enum/parser to its own request-local keys in the existing
Choice authority; Packet remains only the candidate/receipt owner. A label
collision is not a
technical mapping failure:
cross-type ambiguity can use `unclassified`, while same-type
indistinguishability hits the explicit count-one compatibility stop. Exact
refs, the complete 59-binding table, canonical IDs, provenance and retention
stay outside the Context V2.0 model surface; historical active V6 exposure
remains unchanged.

The audit does not mutate Slim v2, activate it, change the current four-block
packet or authorize a second packet builder.

## Historical Context V2.0 and current minimal V2.1 target

The versioned
[LLM Semantic Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
defines the exact implemented non-active completeness baseline. Its candidate
and packet-owned mapping receipt remain version-pinned historical sidecars and
do not replace this packet or the implemented historical Slim View.

The historical
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
supersedes V2.0 as the field-eligibility policy for the implemented non-active
V2.1 candidate. GOAL 8 changes no active packet, Prompt, Choice, request,
provider, managed-asset or runtime bytes.

The same packet factory derives its V2.0 available type set from the
validated semantic-contract authority: every active Pack/Registry type
compatible with the Evidence Bundle source family. The type IDs present in
`typed_options` and `blocked_bindings` are only a private Compiler parity
check; blocked status is not semantic plausibility. The factory uses a
versioned extension of the existing Pack projection for titles and complete
decision-relevant type meaning, and a validated closed-world snapshot of the
existing managed reason catalog for reason meaning. It may not read asset
files or import build scripts at runtime.

The V2.0 contract also fixes its historical key/label split, factored readable
relationships, strict local-response design, packet-owned mapping receipt and
linter-owned sealed-request design. GOAL 4 implements only the renderer and
packet-owned receipt. The V2.0 response profile, linter extension, sealed
request, persistence/replay, provider projection and route remain
`NOT_IMPLEMENTED`. Active packet bytes and hashes remain unchanged.

GOAL 8 implements exactly one non-active V2.1 candidate plus private mapping
receipt in this existing Packet factory. Across the frozen suite it preserves
all ten active payload hashes, renders 45 exact semantic literal occurrences,
restores 12 choices and all 59 bindings, and uses 26,211 model-visible UTF-8
bytes versus 78,621 for historical V2.0. All current choices have distinct
titles, so zero differentiators and zero consumerless value/structure keys are
visible.

The candidate is always `active=false`, `transport_eligible=false` and records
zero provider calls. The existing Choice authority adds the GOAL 9 response
profile without changing Packet bytes or ownership. The same existing Context
Linter authority now consumes the exact candidate and private mapping receipt
through additive `create_context_v2_1`, producing only an inactive
provider-neutral sealed request. No provider adapter or runtime consumer
exists; provider projection remains stopped before GOAL 11.

The selected sources already exist:
`positive_signal` maps to Pack `examples[0]`, `negative_signal` maps to
`counterexamples[0]`, nearest distinction maps to the unique direct rule
against the only other current visible type, and reason `use_when` maps to the
exact first sentence of catalog `meaning`. GOAL 7 implements those mappings;
packet code does not invent or embed replacement wording.
