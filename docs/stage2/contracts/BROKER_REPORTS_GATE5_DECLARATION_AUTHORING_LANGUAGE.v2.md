# Broker Reports Gate 5 Declaration Authoring Language v2

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.24_CLOSED`

Product status: `INACTIVE PROOF`

Date: 2026-08-10

## Purpose

This contract version-replaces the current authoring-language boundary from
G5.19/G5.20. It proves that an independent history-free LLM can describe a
bounded 2025 3-NDFL securities Declaration Definition in semantic terms and
that ordinary code can derive exact runtime bindings without changing the
candidate.

It does not add a runtime capability, published behavior, declaration
artifact, tax rule, case input, runner or product route.

## Failure localization

G5.20 established that its three candidate failures were representation
failures, not evidence that the model needed executable internals:

| G5.20 symptom | Generic ambiguity | v2 rule |
| --- | --- | --- |
| target identity was treated as a compilable requirement | official target identity and producible runtime semantic shared one requirement shape | target owns form/order/period/XSD identity; only produced semantics are requirements |
| semantic behavior I/O was copied into an execution-wrapper binding | the model had to reconstruct two different contract layers | composition contains only capability and optional behavior identity; compiler resolves both exact layers |
| an absent behavior required a synthetic missing ID | gap taxonomy required an identity for something that does not exist | gap describes required semantic and relevant existing identities; absent-object IDs do not exist in the language |

The correction is deliberately generic. The schema and instructions contain no
G5.20 candidate, validator error, expected gap, roadmap or expected requirement
identity.

## Four separate meanings

The language keeps these facts distinct:

1. `official_requirement` and `evidence_refs` state what official evidence
   requires;
2. `runtime_support` states whether supplied runtime capabilities and published
   artifacts can produce that semantic;
3. `compositions` state which existing capability, behavior and artifact
   identities participate;
4. case-time input availability is not model-authored because this authoring
   context contains no case evidence.

The compiler always records the fourth fact as:

```json
{
  "status": "not_evaluated",
  "reason": "no_case_evidence_in_authoring_context"
}
```

This is neither an availability claim nor an incomplete-case claim.

## Sole current owner

`Gate5DeclarationAuthoringLanguageV2Factory` is the sole current v2 payload,
semantic-validator and deterministic-compiler owner. `create` preserves the
G5.21 base replay, while explicitly named additive methods preserve later
repository-truth snapshots.

It reuses official evidence, Runtime Capability Contract v1 and the published
artifact inventory through `Gate5CleanContextDeclarationTrialFactory.create`,
and resolves behavior details through
`Gate5PublishedTypedBehaviorRegistryFactory.create`.

The G5.19/G5.20 language schemas, validators and candidates remain immutable
historical replay evidence. The v2 factory calls the old factory only to obtain
its exact frozen shared evidence/inventory projection; none of the v1 candidate
language or validation rules participates in v2 compilation.

## Model-authored surface

The closed v2 candidate contains only:

```text
definition identity and exact declaration target
bounded scope
ordered official requirements and semantic outputs
runtime_support
semantic compositions:
  capability_id
  optional behavior_ref
  artifact_refs
typed gaps expressed as required semantics
first_blocking_gap_id
```

The model cannot author wrapper input/output contracts, behavior contract IDs,
aggregate status, case-input status, implementation names, code, tools or
synthetic missing-object IDs.

## Deterministic compilation

For every unchanged composition the compiler:

- resolves a proven case-time capability from the frozen v1 projection;
- derives its exact declared inputs and output contract;
- enforces artifact existence and capability role;
- for typed execution, resolves the exact registered behavior input/output
  contract and requires the matching methodology artifact;
- rejects unknown or duplicate identities;
- derives `compilable`, `partially_compilable` or `not_compilable` from ordered
  requirement support;
- requires the first blocker to belong to the first non-supported requirement.

There is no transport, runtime execution, normalization, repair or fallback in
this owner.

## Frozen payload

```text
resource  gate5_declaration_authoring_language.primary.v2.payload.json
schema    broker_reports_gate5_declaration_authoring_language_v2
bytes     24971
sha256    90294e3cbecb8c273db51271646dbc9b6281e4db8f2a8d62bcf16a3571633787
sections  6
```

Bias audit result is `passed`; the only matching forbidden lexical term is
`line 060` inside supplied official evidence.

## Independent trial

Trial `g5.21-primary-2026-08-10-001` supplied the exact frozen payload as the
only application message to a new ephemeral read-only `gpt-5.6-sol` context.
Provider schema, history, retry, follow-up and repair were absent.

The one observable candidate was preserved byte-for-byte:

```text
response bytes   10209
response sha256  8cde1468c6a37917432ec5f6f1c0412107093b2c6d339f64fa8d8d2fe29277fe
JSON parse       passed
closed schema    passed
semantic compile passed
manual repair    0
```

The result contains four requirements, seven resolved compositions and three
typed gaps. Two Appendix 8 requirements are supported. Two Section 2/full
electronic-contract requirements are unsupported. The first blocker is
`section2_calculation_behavior_missing`; no expected gap was supplied.

## Verdict and limits

`G5.21_PROVEN`: the v2 language is precise enough for this independent bounded
Declaration Definition authoring trial. The unchanged candidate uses only real
published identities, distinguishes runtime support from case inputs, compiles
mechanical contracts deterministically and finds the real next unsupported
boundary.

This does not prove taxpayer completeness, case-time executability, Section 2
tax semantics, full declaration serialization or general authoring across
other forms/domains. The candidate remains evidence, not a published package.

## Additive G5.22/G5.23/G5.24 replays

The original G5.21 payload above remains immutable. Two separate factory
methods preserve later repository-truth snapshots:

```text
create_g522_replay  -> adds the published income-group tax-base artifact
create_g523_replay  -> uses Runtime Capability Contract v2
create_g524_replay  -> uses Runtime Capability Contract v3 and both PROJECT v1 artifacts
```

G5.23 also adds one generic language rule: every listed composition must have
all suitable published artifacts required for executable compilation; an
unsupported semantic without such an artifact belongs only in a typed gap.
This corrects the generic ambiguity exposed by the unchanged G5.22 candidate.
It names no expected requirement or next gap.

The frozen G5.23 payload is 26,898 bytes with SHA-256
`62fde21f4bc75d32deebf3ac9c650b4506d5f269d3392c6ba97c3af3695a7a9d`.
One history-free inference produced an exact candidate that passed parser,
schema and compiler without repair, removed the old category-cardinality gap
and independently identified a missing validated Section 2 projection artifact
as the next blocker. This is evidence only; the projection was not implemented.

The G5.24 payload changes only current published truth: PROJECT v1 replaces the
old PROJECT member inside the same five-family capability basis; the Appendix 8
inventory entry moves to the v1 fragment envelope; and the new SHA-pinned
Section 2 projection is present. System instructions, research policy,
official evidence and output schema remain byte-for-byte semantically equal to
the G5.23 replay. Neither prior gap nor an expected next gap appears outside
official evidence.

```text
trial             g5.24-history-free-replay-2026-08-10-001
payload bytes     28631
payload sha256    c69a096ad656ccb0c843930977f7ed12b0e148cd5467528dca06ea6fe08241f3
provider calls    1
retry/follow-up   0/0
candidate bytes   7405
candidate sha256  c2efa5639a8d083ef6f7c9d9cef4f873a1027cdfbcc4d765b80c66555aa8c8c1
parser/schema     passed/passed
compiler          passed
manual repair     0
```

Both G5.23 Section 2 projection gaps are absent. Four of five requirements are
supported; the independently identified first blocker is
`complete_electronic_declaration_assembly_gap`.

The exact candidate remains evidence, not authority. Its semantic output text
mentions income type `003`, although the validated Section 2 fragment emits
only group `02` plus six monetary attributes. Its unsupported full-document
composition also lists two projection artifacts under one PROJECT composition,
although runtime accepts one ref per invocation. The compiler currently checks
artifact identity/role, not composition artifact cardinality. These two
limitations were recorded without retry, follow-up or repair and do not alter
the runtime proof.

## Hard stop

G5.24 does not authorize:

- complete electronic declaration assembly or validation;
- a change to the proven Section 2 calculation or projection semantics;
- a new capability, behavior, artifact, methodology or value kind;
- execution of the candidate over a Financial Case;
- Declaration runner, workflow, DSL, DB, GUI, XML/PDF or product activation;
- manual repair or publication of the model candidate;
- the next runtime slice.

Official CLI separation between final-message capture and provider output
schema, and the JSON Schema subset limitation for Structured Outputs, were
verified on 2026-08-10 in the
[Codex developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
and
[Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
documentation.
