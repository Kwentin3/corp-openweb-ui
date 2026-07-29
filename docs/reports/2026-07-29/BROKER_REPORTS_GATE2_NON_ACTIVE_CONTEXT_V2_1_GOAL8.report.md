# Broker Reports Gate 2 Non-Active Context V2.1 — GOAL 8

Date: 2026-07-29

Status: local functional implementation passed; executable sealed-request
budget remains not proven; immutable GitHub review and Actions check required
before merge.

Base: `origin/main@2d3803652f7faa58baf20ee95f1ae89822177d71`

Branch: `agent/broker-reports-gate2-context-v2-1-goal8`

## 1. Scope and authority

GOAL 8 implements one current non-active
[Context V2.1](../../stage2/contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md)
candidate and one private exact mapping receipt inside the existing
`Gate2FinancialSemanticV6PacketFactory.create`.

The factory still constructs the active four-block V6 packet first. Its exact
payload and hash are unchanged. The V2.1 sidecar then reuses:

- the validated Evidence Bundle for source facts and real hierarchy;
- the Candidate Compilation for exact options and bindings;
- the existing GOAL 7
  `create_minimal_managed_projection` profile for all visible type/reason
  wording; and
- the existing Packet owner for deterministic construction and validation.

No new Packet, projection, Choice, Prompt, request, adapter, provider,
persistence, replay or runtime owner was added.

## 2. Historical separation

Context V2.0 remains exact, version-pinned historical completeness evidence.
Its implementation and managed payload are preserved, but
`Gate2FinancialSemanticV6PacketFactory.create` no longer builds it on the
current per-request path.

Historical hierarchy/tamper tests explicitly invoke the V2.0 builder. Current
architecture tests fail if the Packet path calls that builder or introduces a
parallel V2.1 factory.

## 3. Closed V2.1 candidate

The candidate has exactly five ordered model-visible blocks:

```text
task
source
type_cards
choices
unclassified_reasons
```

It is always:

```text
active = false
transport_eligible = false
provider_calls_total = 0
response_profile_status = not_implemented
```

`source.children` projects only real `table`, `row` and `text segment`
hierarchy. Every non-reference literal occurrence is retained exactly once.
`source.document`, invented `evidence group`, `value_type`, global refs,
hashes, nulls and consumerless local keys are absent.

The interleaved-row regression proves exact occurrence/reference parity even
when real hierarchy grouping differs from the flat input sequence. Equal
literals at distinct source occurrences remain distinct.

## 4. Managed glossary and choices

Every case contains the exact two type cards and exact three reason cards from
the GOAL 7 minimal projection:

```text
projection profile =
broker_reports_gate2_minimal_managed_projection_v1_candidate@1.0.0

model projection SHA-256 =
fae235725094d45d82dfe0eee3fefd4268cf1cd6a2c0aa8a5a7392a4b75acca5

private authority-audit SHA-256 =
fc3379890c73628c891f8b48fef25874f8bfb8551d93bcd682e78b6e9f374657
```

The frozen suite contains 12 choices and 59 exact compiled bindings. All
current choice pairs have distinct managed titles, so none needs a visible
differentiator:

```text
VISIBLE_DIFFERENTIATOR_BINDINGS: 0
BACKEND_ONLY_BINDINGS: 59
VISIBLE_VALUE_KEYS: 0
VISIBLE_STRUCTURE_KEYS: 0
```

A synthetic bounded unit proves that otherwise same-title choices expose only
the minimum differing binding. Type-title and cross-type same-title collisions
fail closed.

## 5. Private exact receipt

The packet-owned receipt binds the candidate to:

- active packet and candidate view hashes;
- exact Context contract/policy versions;
- minimal projection and authority-audit hashes;
- managed family, Pack, reason catalog and Registry identities;
- Evidence Bundle and Candidate Compilation scope;
- every source occurrence pointer, exact refs, lineage and evidence refs;
- every local type and choice restoration;
- every ordered option binding and its visible/backend partition; and
- deterministic presentation order and receipt integrity.

The public validator rebuilds candidate and receipt. Rehashed payload
mutation, removed literal occurrence, reordered choice binding, removed
restoration row and authority/mapping drift are rejected.

Repository-safe rendering contains only identities, hashes, counts, byte
sizes, non-active status and zero-call accounting. No source literal, source
ref or provider payload is committed.

## 6. Exact frozen budgets

| Case | Active V6 bytes | Historical V2.0 bytes | V2.1 bytes |
| --- | ---: | ---: | ---: |
| `syn_successor_v2_unique_cash` | 9,638 | 8,070 | 2,645 |
| `syn_successor_v2_unique_printed_total` | 9,905 | 8,068 | 2,643 |
| `syn_successor_v2_multiple_compatible` | 4,246 | 7,620 | 2,624 |
| `syn_successor_v2_no_registry_type` | 9,770 | 8,065 | 2,640 |
| `syn_successor_v2_missing_discriminator` | 9,145 | 7,921 | 2,584 |
| `syn_successor_v2_detail_vs_subtotal` | 3,822 | 7,560 | 2,584 |
| `syn_successor_v2_adjacent_equal` | 3,724 | 7,556 | 2,580 |
| `syn_successor_v2_adjacent_fx` | 4,066 | 7,624 | 2,624 |
| `syn_successor_v2_optional_missing` | 9,779 | 8,068 | 2,643 |
| `syn_successor_v2_forbidden_neighbour` | 9,875 | 8,069 | 2,644 |
| **Total** | **73,970** | **78,621** | **26,211** |

Results:

```text
aggregate candidate target <= 30000 bytes: PASSED
each candidate <= corresponding active packet: 10/10 PASSED
each Context candidate <= 4500 bytes: 10/10 PASSED
logical request calculation <= 4500 bytes: FEASIBILITY_ONLY
executable sealed request <= 4500 bytes: NOT_PROVEN
reduction from V2.0: 52410 bytes / 66.66 percent
```

The maximum contract-derived complete logical request envelope is 3,522
bytes, below the 4,500-byte target. This is feasibility evidence only. It is
not an executable sealed request result: the Choice-owned V2.1 response
profile is not implemented, no provider envelope was built and no transport
was attempted. No sealed-request budget pass or full GOAL 8 budget closure is
claimed.

## 7. Unchanged boundaries

```text
active V6 payload/hash = unchanged 10/10
active unclassified retention/ownership = exact totality proof
Prompt = unchanged
active Choice/parser = unchanged
managed assets = unchanged
benchmark manifests/expected answers = unchanged
request builder = unchanged
provider adapters = unchanged
runtime routes = unchanged
generated Function bundle bytes = unchanged
provider calls = 0
full benchmark = NOT_RUN
runtime activation = false
```

## 8. Verification

From `services/broker-reports-gate1-proof`:

- the four-file V2.1/Packet/history/architecture proof passed:
  `62 passed`;
- Ruff passed for every changed Python test/source file;
- the dedicated V2.1 proof passed all seven tests;
- active packet byte/hash baselines remained exact for all ten cases;
- all three generated-asset checks passed;
- all three Function bundles rebuilt with zero diff;
- the exact anti-drift CI steps passed `7 passed` and
  `9 passed, 38 deselected`;
- the exact focused CI suite, including the repository privacy guard, passed
  `156 passed`, `5 warnings`, `70.41s`;
- baseline-compatible repository Ruff passed.
- the expanded set of every test module that directly constructs the V6
  Packet passed `138 passed`, including all six totality tests.
- active unclassified expansion retained the exact Evidence Bundle retention
  set and ownership under the new non-active sidecar. A V2.1-local
  unclassified answer cannot yet be tested because its separately owned
  response profile does not exist.
- workflow YAML, safe-receipt JSON and all 15 changed-document relative links
  parsed or resolved successfully;
- `git diff --check` passed;
- two independent fresh local diff reviews passed after the size-guard,
  sealed-request-status and historical-tense findings were resolved.

That expanded run initially exposed two legacy V1 cases whose active packet
is smaller than the complete V2.1 glossary. The constructor had incorrectly
applied the current-suite `candidate <= active` acceptance rule globally.
The fix keeps both size relations as exact acceptance oracles for the ten
governed current cases and restores legacy totality. Neither relation is a
constructor rejection rule for unrelated historical/future inputs; GOAL 9
owns complete-request budget rejection after a V2.1 Choice response profile
exists. The totality module is now part of CI so the regression cannot recur
silently.

The full service suite is deliberately not run because it crosses the
historical full-benchmark proof boundary. No provider command, smoke, retry,
repair or fallback is invoked.

The real GitHub Actions `broker-reports-ci` check and a fresh review of the
actual immutable GitHub diff remain required before merge. Local success is
not represented as a GitHub check.

## 9. Verdict and continuation

GOAL 8 passes its local functional boundary: one deterministic non-active
V2.1 candidate and private exact receipt exist in the sole Packet owner while
active V6 bytes and runtime routes remain unchanged. The executable
sealed-request budget remains explicitly unproven until the separately owned
Choice profile is authorized and exists.

**STOP before GOAL 9:** the program owner must separately authorize a
versioned V2.1 response profile in the existing Choice authority, or amend the
program. This GOAL does not authorize GOAL 9, provider transport or GOAL 10+.
