# Broker Reports Gate 2 — Minimal Model Surface GOAL 5 Contract

Date: 2026-07-29

Status: `PASSED_LOCAL_ACCEPTANCE_READY_FOR_REVIEWED_GREEN_PR`

Base revision: `3e48adc11d41f5b51d388800b2e017a85b118553`

Branch:
`codex/broker-reports-gate2-minimal-model-surface-goal5`

## 1. Outcome

GOAL 5 defines one closed, documentation-only
[Minimal Model Surface v1](../../stage2/contracts/BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
for the future non-active Context V2.1 candidate.

The contract keeps only:

- one short task;
- exact source literals once, readable meaning and real source structure;
- one compact managed card per visible type;
- local choices with readable titles and only choice-specific
  differentiators;
- one compact managed card per allowed unclassified reason.

It explicitly removes the current V2.0 full domain manuals, common bindings,
administrative fields and information-free source wrapper from the future
target. Exact IDs, authority pins, complete bindings and restoration mappings
remain backend/private.

This is not a V2.1 implementation. The current active V6 packet, implemented
non-active V2.0 sidecar, managed assets, Pack projection, Choice, Prompt,
provider route, expected answers and runtime remain unchanged.

## 2. Context Bootstrap and ownership

The canonical inputs were:

- the architecture authority map;
- the exact implemented LLM Semantic Context V2.0 contract and GOAL 4
  evidence;
- the Financial Semantic Pack and its current shared projection;
- the Financial Decision Reason Catalog;
- Evidence Bundle, Typed Option, Packet, Choice and Exact Evidence contracts;
- the governing GOAL 5 through GOAL 9 sequence.

The affected domain is the existing Semantic Matcher. The new contract owns
only model-field eligibility and necessity. Construction remains in
`Gate2FinancialSemanticV6PacketFactory.create`; type wording remains in the
Pack; reason wording remains in the reason catalog; the response stays in the
Choice authority; the complete-request linter and provider adapters remain
unchanged.

No second Packet factory, Pack, catalog, projection owner, Choice schema,
adapter, GUI or runtime route is introduced.

## 3. Actual V2.0 surface audit

The audit instantiated the existing ten frozen semantic fixtures locally and
serialized each implemented non-active V2.0 payload with the maintained
minified UTF-8 convention. It performed no provider call.

| V2.0 block | Aggregate bytes | Share |
| --- | ---: | ---: |
| `type_cards` | 49,410 | 62.85% |
| `unclassified_reasons` | 19,590 | 24.92% |
| `source` | 4,645 | 5.91% |
| `choices` | 1,714 | 2.18% |
| `task` | 1,310 | 1.67% |
| `shared_relationships` | 1,128 | 1.43% |
| root keys and syntax | 824 | 1.05% |
| **total** | **78,621** | **100.00%** |

The repeated type and reason manuals account for 69,000 bytes, or 87.76% of
the aggregate payload:

- every case repeats the same two full type cards;
- every case repeats the same two full reason cards;
- the four zero-choice cases still carry the same 6,900-byte combined
  glossary blocks;
- the frozen suite contains 45 exact source-literal occurrences and 12
  choices;
- its 35 readable relationships divide into 24 bindings common to all
  choices in their case and 11 choice-specific relationships.

The current surface therefore spends most bytes on invariant domain
administration rather than the source-dependent choice.

## 4. Accepted minimal field boundary

The contract contains a complete canonical `P01`–`P18` provider-neutral
request/response protocol
allowlist and a closed `M01`–`M32` semantic-payload allowlist. Every row
records:

- exact field/path;
- cardinality and authority;
- current decision consumer;
- an explicit “yes” answer explaining how omission can change the correct
  semantic choice.

The future ordered semantic payload root is:

```text
task
source
type_cards
choices
unclassified_reasons
```

The `P` allowlist is the canonical provider-neutral logical request. It
forbids model-visible schema names, titles and descriptions. Exact OpenAI and
Anthropic native-envelope equivalence remains GOAL 10 work; GOAL 5 claims no
provider-profile compatibility.

Notable decisions:

- `source.children` preserves the real hierarchy without the V2.0
  information-free `document` wrapper;
- `value_type` is backend-only; the single visible `meaning` must be
  decision-sufficient or construction fails closed;
- source `label`, structural roles and local source keys require a recorded
  per-occurrence decision consumer; mere presence/distinctness is
  insufficient;
- the current two type cards remain visible even when `choices=[]`;
- a type card has only local key, title, definition, primary positive signal,
  primary negative signal and one nearest-type distinction when needed;
- a choice has only local key, readable title and concrete differentiators;
- current cross-type choices have no differentiators because their managed
  titles already differ; only facts needed between otherwise same-title
  selectable records may appear;
- a reason card has only code, title and one `use_when` sentence.

The choice has no visible `type_key`. Its exact title maps it to the current
two-type glossary, while the private receipt restores its exact type and Typed
Option. Adding a second visible identity would not change the current
semantic choice.

## 5. Closed forbidden surface

The contract makes every unlisted field forbidden and explicitly removes:

- full role schemas and role administration;
- lifecycle and compatible-source administration;
- all model-visible identities, versions and hashes;
- synonym arrays and raw example/counterexample arrays;
- full ambiguity/model guidance and multi-distinction manuals;
- validation/materialization/retention/replay guidance;
- reason meaning, negative guidance and reciprocal contrasts;
- common or repeated bindings;
- unused aliases and the V2.0 `shared_relationships`/`applies_to` structure;
- source-reference literals, invented structure, copied literals and
  generated summaries;
- expected answers, benchmark labels, provider metadata and hidden traces;
- nulls, empty optional fields and compensating provider-visible prose.

The contract also classifies every row of the V2.0 allowlist as retained
protocol, minimized, backend-only or forbidden. Historical V2.0 remains
unchanged.

## 6. Exact managed projection mappings

GOAL 5 closes the legal managed-source mapping instead of leaving semantic
selection to Packet code:

1. type title/definition come from the exact Pack fields;
2. `positive_signal` is exact `examples[0]`;
3. `negative_signal` is exact `counterexamples[0]`;
4. the current nearest competitor is the only other visible type, and its
   distinction is the unique exact direct Pack rule against that type;
5. reason code/title come from exact catalog fields;
6. reason `use_when` is the exact first sentence of catalog `meaning`, with a
   closed byte-level sentence-boundary rule.

Pack order is normative, and GOAL 5 explicitly selects index `0`; the raw
arrays remain backend-only. GOAL 7 must implement only these mappings in one
versioned/hash-identified profile inside the existing projection owner.
Packet/Prompt/adapter wording, summaries and alternative selection are
forbidden.

The current one-plausible-type/no-safe-record gap remains a GOAL 6 stop.
No reason or expected answer changes in GOAL 5.

A canonical backend-only audit object containing the two exact projected type
cards and two exact projected reason cards serializes to 1,939 minified UTF-8
bytes and has SHA-256
`5f48dbc3d870a8289f0463d0a1db5dcae44fdbe0efb63bd7b21008ca289033a1`.
The object includes canonical input IDs only for audit reconstruction; those
IDs remain absent from the model surface.

## 7. Representative examples

The contract contains JSON examples for:

- a frozen synthetic cash source with exact literals once;
- two title-distinct readable local choices with no redundant bindings;
- a compact cash type card using the accepted exact current managed mappings;
- both compact reason cards using exact managed one-sentence mappings.

No customer/private values, refs, paths, provider payloads or hidden traces
are included.

## 8. Change scope

Actual change classes:

```text
NEW_NORMATIVE_CONTRACT: ONE
CANONICAL_ROUTING_DOCS: UPDATED
NEW_DATED_REPORT: ONE
NEW_REPOSITORY_SAFE_RECEIPT: ONE
CHANGED_FILES_TOTAL: FIFTEEN
RUNTIME_PYTHON: ZERO
MANAGED_ASSETS: ZERO
SEMANTIC_PACK_BYTES: ZERO
TEST_CODE: ZERO
GENERATED_BUNDLES: ZERO
GITHUB_WORKFLOW: ZERO
PROVIDER_CALLS: ZERO
```

Historical GOAL 4 report and receipt are not edited. They remain immutable
evidence for the implemented V2.0 baseline.

## 9. Validation

All local validations used the maintained repository entrypoints:

- all three generated managed-asset checks passed;
- all three generated Function bundles rebuilt with zero byte diff;
- baseline-compatible Ruff correctness checks passed;
- the exact focused CI suite passed: 93 tests, 5 warnings, 35.21 seconds;
- the full service suite passed: 1,907 tests, 20 skipped, 5 warnings,
  620.06 seconds;
- changed-file accounting passed: 15 files, with zero runtime, managed-asset,
  test, generated-bundle or workflow files;
- 17 fenced JSON blocks parsed;
- 398 relative Markdown links resolved with zero missing targets;
- both type mappings and both reason mappings matched their managed sources
  byte-for-byte;
- the complete `P01`–`P18` and `M01`–`M32` ranges, future task, forbidden
  fields and GOAL 6→7→8→STOP→9 sequence passed stale-semantics checks;
- focused architecture/privacy tests, `git diff --check`, receipt JSON parsing
  and receipt integrity passed;
- independent local reviews found no unresolved blocker/high issue. One
  medium issue was corrected: GOAL 8 now owns only the non-active Context
  V2.1 Packet candidate. A subsequent sequence finding is closed by an
  explicit STOP: GOAL 9 remains linter-only and cannot proceed until a
  separately authorized versioned V2.1 response profile exists in the
  existing Choice authority.

The repository-safe
[receipt](BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE_GOAL5_CONTRACT.receipt.safe.json)
contains the aggregate audit, closed scope, mapping identity and exact test
counts. It contains no customer/private values, provider payloads, filesystem
paths or hidden traces.

The real GitHub Actions `broker-reports-ci` check and fresh review of the
actual immutable GitHub diff remain required on the PR head before merge.
They are deliberately not represented as already passed local checks.

## 10. Verdict and continuation

GOAL 5 passes local acceptance as one documentation-only Minimal Model Surface
contract. It is ready for a separate reviewed-green PR; it is not a runtime
implementation or activation claim.

The only next program goal is GOAL 6 from a fresh branch based on the merged
GOAL 5 revision. Until that merge, GOAL 6 is blocked. GOAL 7, Context V2.1
implementation, linter work, expected-answer changes and provider calls remain
unauthorized.

The STOP after GOAL 8 does not block GOAL 6 or GOAL 7. It does block GOAL 9
until the program owner explicitly authorizes the missing Choice-owned V2.1
response profile or amends the governing sequence.
