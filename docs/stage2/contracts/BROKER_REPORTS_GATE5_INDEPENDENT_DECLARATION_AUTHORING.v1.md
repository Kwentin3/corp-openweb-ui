# Broker Reports Gate 5 Independent Declaration Authoring v1

Status: `CURRENT SUPPORTING CONTRACT`

Goal status: `G5.20_PARTIALLY_PROVEN`

Product status: `INACTIVE PROOF`

Date: 2026-08-10

## Purpose

This contract version-replaces only the G5.19 experiment transport and verdict.
It tests whether a history-free LLM can author a machine-readable, statically
compilable subset of the 2025 3-NDFL securities-disposal declaration and find
the first real unsupported boundary from supplied official evidence, Runtime
Capability Contract v1 and the published-artifact inventory.

It does not add declaration semantics, execute a case, publish model output or
activate a product route.

## Reused semantic owner

`Gate5CleanContextDeclarationTrialFactory.create` remains the sole maintained
payload and neutral-validator owner. G5.20 adds only two methods to its result:

```text
independent_pre_inference_record
parse_candidate_response / validate_candidate_response
```

The parser accepts exactly one UTF-8 JSON object. It does not extract a fenced
block, select one of several objects, normalize fields or repair a candidate.
Provider invocation remains outer experiment infrastructure and is not an
application client or an alternative to `Gate2StructuredModelClientFactory`.

## Technical harness

G5.20 removed the provider-level strict JSON Schema option. The complete closed
Draft 2020-12 schema remained visible inside the frozen semantic payload and
the unchanged local validator still enforced it after capture.

The selected route was:

```text
one exact user-message payload
-> empty ephemeral read-only model context
-> assistant final-message file
-> exact UTF-8 JSON-object parser
-> unchanged schema and repository validator
```

A non-semantic canary reached real inference and returned the requested 68-byte
JSON object. It received no declaration evidence, capability inventory or
published artifacts. This proved the capture/parser seam before the observable
semantic result.

Official OpenAI documentation treats `--output-last-message` as a downstream
capture mechanism and `--output-schema` as a separate validation option. It
also states that Structured Outputs supports only a JSON Schema subset and
rejects unsupported strict schemas. Verified 2026-08-10:
[Codex developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
and
[Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## Frozen semantic input

G5.20 reused the exact G5.19 attempt-002 payload without semantic edits:

```text
resource  gate5_clean_context_declaration_trial.primary.v1.payload.json
bytes     27013
sha256    a3ad620016c93eff08a7f79cdb24f86cdcc81b0dd16ce7a68be2660d760fac46
```

It still has exactly six sections and its bias audit has no forbidden hit
outside official evidence. No expected gap, prior candidate, Gate report,
roadmap or follow-up instruction was supplied to the model.

## Independent inference record

Both semantic submissions used the same frozen bytes, model and isolation:

```text
provider       openai_codex_cli
client         codex-cli 0.147.0-alpha.6.5
model          gpt-5.6-sol
reasoning      high
session        ephemeral new session
workspace      empty temporary directory
sandbox        read-only
user config    ignored
exec rules     ignored
provider schema none
repair         0
```

Attempt `001` reached inference, but the outer experiment supplied a corrupted
Cyrillic absolute output path. The process returned success while no readable
final-message file existed. The response was never observed, hashed, parsed or
eligible for selection.

Attempt `002` changed only output-file routing to the already proven temporary
path pattern. Semantic payload bytes did not change. It completed inference and
produced exactly one observable JSON object:

```text
response bytes   20848
response sha256  093879f7e08cbba68ce0ab0df938acf86b8a0a0708cf8c04f0a6818848d15a75
JSON parse       passed
JSON Schema      passed
manual repair    0
follow-up        0
```

The inaccessible first response prevents candidate cherry-picking: there was
only one observable candidate. The capture failure and recovery remain an
explicit limitation of the experiment record.

## Candidate result

The model independently returned a `partially_compilable` Definition with ten
requirements and five gaps. It correctly selected the existing Appendix 8
projection for three exact conditionally compilable units:

```text
appendix8_five_operation_semantics
appendix8_operation_code_01
appendix8_electronic_occurrence
```

It also discovered a real unsupported boundary without a supplied expected-gap
hint: the current inventory ends at Appendix 8 and does not connect its accepted
expense to a group-bound Section 2 calculation or provide the required Section
2 projection/behavior/contracts.

The model's first blocker was
`appendix8_expense_to_section2_gap`. Repository truth supports the underlying
absence claim. It is a better experimental result than forcing the candidate
to reproduce an expected historical gap label.

## Deterministic audit

The candidate passed the closed JSON Schema, exact target and authoring-boundary
checks. The unchanged neutral semantic validator then failed at
`requirements[0]` with:

```text
gate5_clean_context_candidate_case_evidence_overclaim
```

The full non-mutating repository audit localized three authoring defects:

1. `target_order_and_period` was marked end-to-end available and compilable
   without a capability binding;
2. `appendix8_repeated_occurrences` used the correct registered behavior and
   aggregation identities but declared the behavior's semantic input contract
   in place of the typed-execution wrapper's exact contract-identity inputs;
3. `section2_calculation_behavior_gap` used
   `missing_published_behavior` while leaving its required
   `missing_behavior_id` null.

Five of six capability bindings validated against repository truth; four of
five gap objects passed their taxonomy invariants. The model output remains
unchanged evidence and is not a valid published Definition.

## Verdict

`G5.20_PARTIALLY_PROVEN`.

The clean LLM understood a real supported subset, used only supplied identities
and found the real Section 2 boundary. It did not invent a capability, artifact,
formula, case value or tax rule. However, it did not produce a wholly valid
compilable package because three exact authoring-contract invariants failed.

The localized problem is the authoring boundary/context representation, not a
need for a new runtime primitive. The experiment therefore supports continued
Declaration Definition authoring work but does not authorize publication,
execution or runtime expansion.

## Hard stop

G5.20 does not authorize:

- manual repair or publication of the candidate;
- a new capability, behavior, artifact, methodology or value kind;
- a Declaration runner, workflow DSL, DB, GUI, XML/PDF or product activation;
- a claim that independent authoring is fully proven.

A later trial may refine only the generic authoring contract/context so exact
wrapper inputs, static metadata and gap-type invariants are clearer. It requires
separate explicit authorization. Runtime changes are not justified by this
result.
