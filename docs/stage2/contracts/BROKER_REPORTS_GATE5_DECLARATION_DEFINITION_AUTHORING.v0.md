# Broker Reports Gate 5 Declaration Definition Authoring v0

Status: inactive proof contract. G5.16 validates one bounded agent-authored
candidate but does not activate a declaration runtime. Blind anti-bias model
authorship is not proven by this revision.

## Purpose

This boundary asks whether official 3-NDFL requirements can be compared with
the G5.15 Runtime Capability Contract and the bounded published-artifact
inventory to produce a small machine-readable Declaration Definition.

The boundary is:

```text
official authoring evidence
        + runtime capability model projection
        + published artifact inventory
        + closed output schema
        -> agent-authored candidate
        -> deterministic static validation
```

It is not a case-time executor, workflow language, tax engine or publication
system.

## Sole owner

`Gate5DeclarationDefinitionAuthoringFactory.create` is the only construction
entrypoint. It:

1. loads one SHA-256-pinned authoring context package resource;
2. obtains the unchanged G5.15 model projection through
   `Gate5RuntimeCapabilityContractFactory.create`;
3. resolves methodology artifacts through the existing trusted-methodology
   authority;
4. validates the current projection artifact through its existing owner;
5. constructs a static candidate validator;
6. performs no model call, case read, calculation or declaration execution.

The resources are:

```text
gate5_declaration_definition_authoring_context.v0.json
gate5_declaration_definition_candidate.ru_3ndfl_2025_securities.v0.json
```

Both are LF-pinned package resources so their raw hashes are stable across
Windows checkouts.

## Exact model-visible payload

`model_payload()` exposes exactly six sections:

```text
system_instructions
research_policy
runtime_capabilities
published_artifact_inventory
official_evidence
output_schema
```

It excludes Python owner names, repository paths, SQL/storage details, prior
Gate reports and case-time research tools. The high-level system/research
sections do not name Section 2, line 060 or an expected group-tax-base gap.
Official evidence remains complete enough to contain those official
requirements; excluding them would bias the research in the opposite
direction.

The authoring context uses the official FNS order page and four attachments:
the form, filling procedure, electronic format and XSD. Attachment SHA-256
values are bound in the context. Previous G5 reports are not evidence inputs.

## Published-artifact inventory

The inventory contains only four relevant repository-published artifacts:

| Artifact | Version | Runtime relation |
| --- | --- | --- |
| `ru-ndfl-securities-proof` | `2026.0-experimental` | executable through `execute_published_calculation_behavior_v0` |
| `ru-ndfl-securities-tax-model-proof` | `2026.0-experimental` | published methodology, no public capability use |
| `ru-ndfl-securities-tax-model-proof` | `2026.1-experimental` | accepted member binding for `aggregate_complete_category_scope_v0`; no public member producer |
| `ru-3ndfl-2025-appendix8-securities-proof` | `2026.0-proof` | validated projection for direct projection and nested aggregation output |

This is deliberately not a generic artifact registry. Methodology references
must resolve through the existing G5.8 authority, while the projection
identity/version must equal the existing G5.12 resource.

## Minimal Definition shape

The candidate root contains only:

```text
identity/version/status
target declaration identity
bounded scope
requirements
gaps
findings
authoring provenance
```

Each requirement is one static compilation unit. A compilable unit references
exactly one proven `case_time` capability and declares all of its boundary
inputs. There is no ordered `steps` or executable `action` field. A dependency
between units is therefore an explicit contract boundary, not an interpreter
instruction.

The current candidate is `partially_compilable`:

- category aggregation is statically compilable when its exact scope,
  compatible operation members and completeness evidence are supplied at the
  boundary;
- direct Appendix 8 projection is statically compilable when all five stable
  semantics are supplied;
- production of compatible operation members from current case evidence has no
  public capability;
- the next official group-bound tax-base requirement has no reviewed published
  behavior.

`COMPILABLE` here means capability/artifact/I/O compatibility for the declared
boundary inputs. It does not claim an end-to-end Financial Case path.

## Deterministic validation

The validator rejects unless all of the following hold:

1. context and candidate resources match their raw SHA-256 pins;
2. every object has the exact closed key set;
3. the target identity equals the official-evidence declaration identity;
4. every evidence reference resolves inside the supplied official evidence;
5. every capability ID resolves through G5.15, is `proven` and is `case_time`;
6. a compilable unit has exactly one capability, compatible declared input
   contracts and the exact capability output contract;
7. every artifact identity resolves and its declared role is compatible with
   the referenced capability;
8. every unresolved requirement has linked gaps and every gap links back to
   exactly that requirement;
9. gap-type-specific facts remain consistent;
10. arbitrary `action`, `steps`, expression, formula, code, command and tool
    fields are absent.

Unknown capability references fail as
`gate5_declaration_definition_capability_unsupported`. There is no alias,
fallback, dynamic import or generated capability.

## Gap classification

The closed gap taxonomy is:

```text
missing_runtime_capability
missing_published_behavior
missing_input_type
missing_artifact
missing_evidence
```

The candidate uses two distinct types:

- `missing_runtime_capability`: current case evidence cannot be turned into the
  operation-model members required by aggregation through a published
  capability;
- `missing_published_behavior`: deterministic calculation is a known runtime
  meaning, but no reviewed published behavior derives the official group-level
  tax base.

The second statement is backlog evidence, not permission to implement the
behavior or change G5.15.

## Independence boundary

The stored system/research payload is structurally anti-biased: it contains a
high-level securities declaration research task and no expected downstream gap
hint. The candidate was authored in the current LLM-assisted engineering
session.

However, the primary agent also received the governing G5.16 addendum, which
contained expected examples, and no separate clean-context model call was
available. The candidate therefore records:

```text
trial_independence = structural_prompt_only_not_blind_to_governance_goal
```

This prevents the repository from claiming that independent model reasoning
was proven when only prompt structure and candidate validity were proven.

## Hard stop

This contract does not authorize:

- a new runtime capability or calculation behavior;
- production case calculation;
- Section 2 implementation;
- a new human input type or research capability;
- XML/PDF output;
- managed publication, GUI or activation;
- a generic workflow runner, rules DSL or plugin registry.
