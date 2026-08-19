# Broker Reports Gate 5 Clean-Context Declaration Authoring v0

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.19_NOT_PROVEN`

Product status: `INACTIVE PROOF`

Date: 2026-08-10

## Purpose

This boundary tests whether one history-free LLM context can derive a bounded,
machine-readable Declaration Definition from only:

```text
general authoring instructions
+ evidence policy
+ Runtime Capability Contract v1 model projection
+ published artifact inventory
+ normalized official FNS evidence
+ neutral closed output schema
```

It does not execute a declaration, add runtime behavior, publish tax policy or
activate a product route.

## Sole maintained owner

`Gate5CleanContextDeclarationTrialFactory.create` is the only maintained
payload and neutral-validator construction entrypoint. It:

1. reuses the exact official-evidence section already hash-pinned by the G5.16
   authoring owner;
2. obtains the current semantic projection from
   `Gate5RuntimeCapabilityContractV1Factory.create`;
3. resolves methodology identities through the existing trusted authority;
4. resolves registered behavior/input/output pairs through
   `Gate5PublishedTypedBehaviorRegistryFactory.create`;
5. validates the current projection artifact through its existing owner;
6. freezes and audits one exact six-section model payload;
7. validates a returned candidate without knowing an expected concrete
   requirement or gap.

The owner performs no case read, tax calculation, runtime execution or
provider call. The isolated Codex CLI call used by G5.19 is outer experiment
infrastructure authorized only by this Goal. It creates no application model
client, control, smoke, UI or production path, and it does not replace
`Gate2StructuredModelClientFactory.create`.

## Neutral validator boundary

The G5.16 validator was not reused because it is pinned to capability v0 and
requires specific `first_runtime_composition_gap_id` and
`first_downstream_declaration_gap_id` findings with preselected gap classes.

The G5.19 validator instead checks only:

- the closed candidate schema and exact declaration target;
- supplied official evidence references;
- proven case-time capability identities from v1;
- exact declared capability input/output contracts;
- existing published artifact identities and capability roles;
- exact registered behavior/input/output contract pairs;
- supported/unsupported requirement and gap cross-references;
- no current-case-evidence overclaim;
- the declared no-history/no-repair authoring boundary.

It contains no expected declaration requirement ID, group-tax-base behavior,
Section 2 special case or expected gap ID.

## Frozen clean input

The successful payload freeze candidate has exactly these logical sections:

```text
system_instructions
research_policy
runtime_capabilities
published_artifact_inventory
official_evidence
output_schema
```

Trial `g5.19-primary-2026-08-10-002` is bound to:

```text
resource:
  gate5_clean_context_declaration_trial.primary.v1.payload.json
bytes:
  27013
sha256:
  a3ad620016c93eff08a7f79cdb24f86cdcc81b0dd16ce7a68be2660d760fac46
```

The mechanical bias audit found no forbidden term outside official evidence.
The only allowed hit was `line 060` inside the normalized official evidence.
The model-visible application input was one user message whose content bytes
were exactly the frozen payload bytes; conversation history was absent.

## Invocation profile

Both pre-inference attempts used:

```text
provider       openai_codex_cli
client         codex-cli 0.147.0-alpha.6.5
model          gpt-5.6-sol
reasoning      high
output         strict JSON Schema
session        ephemeral new session
workspace      empty temporary read-only directory
user config    ignored
exec rules     ignored
retry          0
repair         forbidden
```

Provider-internal system instructions are not claimed as application-owned
message bytes. The recorded clean-context claim is limited to project-visible
application input, empty project workspace and absent conversation history.

## Trial outcome

No inference completed.

The first frozen identity, `g5.19-primary-2026-08-10-001`, was rejected by the
strict-output adapter because `uniqueItems` was not permitted. Per the freeze
rule, its bytes and identity were retained rather than edited.

A second identity changed only the strict-schema representation and was frozen
separately. It was rejected before inference because the nested `const` schema
for `registered_behavior.schema_version` did not also declare an explicit
`type`.

Exact totals are:

```text
provider requests             2
completed inference calls     0
model responses               0
structured candidates         0
manual candidate repairs      0
within-trial retries           0
```

The safe errors are recorded in the dated blind-trial record. Exact provider
stderr remains outside Git because it repeats the complete provider-visible
payload and is not needed for the safe verdict.

## Verdict

`G5.19_NOT_PROVEN`.

This result does not show that a clean LLM can or cannot author the requested
Definition. It shows that the current authoring output schema was not accepted
by the selected strict-output provider profile, so the experiment never
reached model reasoning.

The localized problem is:

```text
authoring output schema
<-> selected strict-output provider profile
```

It is not evidence of a missing runtime capability, missing tax behavior,
artifact gap or model authoring limitation.

Official OpenAI documentation states that Structured Outputs accepts only a
JSON Schema subset and rejects unsupported strict schemas. It also requires
closed objects and full required-key declarations. Verified 2026-08-10:
[Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## Context size

Compared with G5.16, the final frozen G5.19 payload grew from `15,747` to
`27,013` bytes (`+71.5%`). Runtime capabilities grew only from `6,775` to
`7,461` bytes (`+10.1%`). Most growth came from the machine JSON Schema and the
typed artifact inventory, not Runtime Capability Contract v1.

The current total token proxy is `6,754` (`UTF-8 bytes / 4`). This does not
show a capability-contract size problem. No size optimization is authorized or
needed before schema-profile compatibility is corrected.

## Hard stop

G5.19 does not authorize:

- a third iterative model attempt;
- mutation of either frozen attempt;
- manual candidate construction or repair;
- a new capability, behavior, artifact, input kind or methodology;
- a runtime, workflow engine, Declaration runner, DB, GUI or activation;
- a claim that the clean-context authoring hypothesis passed or failed
  semantically.

Any further clean-context call requires an explicit new authorization after a
deterministic selected-provider schema-subset preflight exists. No dependent
engineering slice is authorized by this contract.
