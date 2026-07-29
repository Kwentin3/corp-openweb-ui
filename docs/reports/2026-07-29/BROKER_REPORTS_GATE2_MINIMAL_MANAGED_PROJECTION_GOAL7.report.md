# Broker Reports Gate 2 Minimal Managed Projection — GOAL 7

Date: 2026-07-29

Status: local acceptance passed; immutable GitHub review and Actions check
required before merge.

Base: `origin/main@251df02530005d227413e3c1188b8717061c929f`

Branch:
`agent/broker-reports-gate2-minimal-managed-projection-goal7`

## 1. Scope and authority

GOAL 7 implements one inactive versioned minimal Pack/reason projection. It
reuses:

- the same managed asset-family ID and deterministic builders;
- the single closed-world
  `load_gate2_financial_semantic_model_assets` loader;
- the existing shared
  `Gate2FinancialSemanticV5ProjectionFactory`; and
- the unchanged Semantic Pack v1 and decision-reason catalog v2 wording.

No Packet, Choice, Prompt, request, adapter, provider, persistence or replay
owner was added or changed. Context V2.1 remains GOAL 8.

## 2. Same-family v3 packaging

The additive family v3 manifest has semantic version `1.2.0`,
`runtime_activation=false`, exactly three inherited OpenWebUI assets and
exactly seven dependencies:

1. the four exact family-v1 base dependencies;
2. decision-reason catalog v2;
3. its generated v2 JSON Schema; and
4. its existing v2 validator.

Its exact predecessor is immutable family v2 `1.1.0`:

```text
v2 manifest integrity =
4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d

v2 manifest Git-blob SHA-256 =
4ef70eba07bea24332a0909e4c9cb68c82854197a11fb2e78f47c3d88cf3d586
```

Family v3 identity:

```text
manifest integrity =
8d48e23a876844376443eeb357bb381fe0443c2bf1525657b6f81979408c630c

manifest Git-blob SHA-256 =
34c7c0528d1d4954681e36353f9b82c89e324955ce5916cb5c6b0588e75e85f3

manifest schema Git-blob SHA-256 =
5f63f716c53440c88851de63d54c9c14ba708ff64ecc3599af6c7bed93d28020

catalog-v2 schema Git-blob SHA-256 =
d576e9368272f8bf6dd46250e9d798e7bf40c1dd56f98216262d770a12c2aa24
```

The top-level composition stays exact family-v1 composition and remains
compatible with the active two-reason decision-v1 contract. Catalog v2, its
schema and validator are referenced only inside the inactive minimal profile.
It is not represented as an active response-code authority.

## 3. Closed-world loader profile

The new loader profile is
`minimal_model_surface_v1_candidate`. It returns:

- exact inactive family-v3 identity;
- exact inactive projection-profile identity;
- the complete byte-exact Semantic Pack v1 object; and
- the complete byte-exact decision-reason catalog v2 object.

Profile identity:

```text
broker_reports_gate2_minimal_managed_projection_v1_candidate@1.0.0
runtime_activation = false
response_profile_status = not_implemented
transport_eligible = false
```

Closed-world candidate payload SHA-256:
`6211a7668deb14191cb2a215d726d4e7782e43e4834477cb0fe49e86510c62ca`.

The default active loader output remains
`b80eed8b9a41fa039a9a8d961c972817ae840ce81d7c163de624b7d5a4ec123b`.
The historical Context V2.0 embedded payload remains
`99be5272ebab4e69e2533391f381bd27682496148f760e1e4a171f9e7162cdad`.

## 4. Exact minimal projection

`Gate2FinancialSemanticV5ProjectionFactory.create_minimal_managed_projection`
is an additive profile method on the existing owner.

The model payload contains only:

```text
type_cards
unclassified_reasons
```

For the exact current two-type Pack it assigns `type_1`, `type_2` in Pack
order and projects only:

- exact managed title and definition;
- exact `examples[0]` and `counterexamples[0]`;
- the other visible local type key; and
- the unique exact direct distinction against that other type.

For all three ordered catalog-v2 reasons it projects only exact `code`, exact
`human_title`, and the exact first sentence of `meaning` under the closed
U+002E plus ASCII-space/end rule.

Canonical model payload:

```text
UTF-8 bytes = 2102
SHA-256 =
fae235725094d45d82dfe0eee3fefd4268cf1cd6a2c0aa8a5a7392a4b75acca5
```

Backend-only authority audit SHA-256:
`fc3379890c73628c891f8b48fef25874f8bfb8551d93bcd682e78b6e9f374657`.

The active historical projection remains exactly 3,591 bytes with SHA-256
`6d17d46089b91cfb197dcad12f89635c5879173b6f2175d3810e6dd968361256`.

## 5. Fail-closed behavior

The implementation rejects:

- a visible Pack set with one or three types;
- absent or empty primary positive/negative signals;
- missing or duplicate direct reciprocal distinctions;
- catalog identity, integrity, order or reason-set drift;
- a reason meaning without the exact first-sentence boundary; and
- payload tampering even when the attacker recomputes the supplied hash.

The emitted payload excludes canonical type IDs, source hashes, profile
identity, Pack arrays, roles, synonyms, administrative catalog fields,
contrasts and selection boundaries. Exact managed human wording does not
appear as a Python literal in the projection or generated loader source.

## 6. Historical and active invariants

Repository comparison and deterministic tests preserve:

```text
family v1 bytes = unchanged
family v2 bytes = unchanged
Semantic Pack v1 bytes = unchanged
decision-reason catalog v1 bytes = unchanged
decision-reason catalog v2 bytes = unchanged
active decision/Choice code set = unchanged
Prompt bytes = unchanged
Packet source = unchanged
provider adapters = unchanged
runtime activation = false
provider calls = 0
full benchmark = NOT_RUN
```

The generated domain-source-fact bundle changes only because it embeds the
updated maintained closed-world model-assets/projection modules. Bundle parity
is deterministic.

## 7. Verification

From `services/broker-reports-gate1-proof`:

- both managed-asset builders passed `--check`;
- all three Function bundles rebuilt deterministically and architecture
  parity passed;
- Ruff baseline correctness checks passed;
- the exact GitHub Actions focused suite passed: `135 passed`, `5 warnings`,
  `34.20s`;
- the additional V5/V2.0/model-input regression set passed;
- all 12 dedicated GOAL 7 tests passed;
- `git diff --check` passed.

The full service suite was deliberately not run because it crosses the
historical full-benchmark proof boundary. No provider command, smoke, retry,
repair or fallback was invoked.

Two fresh read-only reviews found three issues: the missing third governing
reason mapping, an over-broad catalog-v2/decision-v1 family composition, and a
stale owner routing anchor. The final diff adds the exact managed third
sentence to the governing contract, scopes catalog v2 only to the inactive
profile, preserves the active decision-v1 composition/code authority, and
pins all three public profile methods on the single existing projection
owner. Re-review found no unresolved issue.

The real GitHub Actions `broker-reports-ci` check and a fresh review of the
actual immutable GitHub diff remain required before merge. Local success is
not represented as a GitHub check.

## 8. Verdict and continuation

GOAL 7 passes local acceptance as one exact inactive managed projection.
Runtime routes and provider execution remain unchanged.

GOAL 8 may begin only after this exact GOAL 7 head receives fresh GitHub diff
review, passes the real Actions check and is merged into `main`. GOAL 8 may
build only the non-active Context V2.1 Packet candidate and private mapping
receipt through the existing Packet owner.

The STOP before GOAL 9 remains: a separately authorized/versioned V2.1
response profile must first exist in the current Choice authority, or the
program must be amended.
