# G5.39AG - Consumer-First Projection Contract

Verified: 2026-08-12

Mode: autonomous research plus test-first inactive implementation

Terminal: `CONSUMER_FIRST_PROJECTION_CORE_PROVEN`

Profile boundaries unproven: `refund_available`, `balanced`,
`multiple_budget_allocations`, `empty_budget_allocations`

## Decision

Yes, for the bounded semantic-valid supplied case the representation layer can
produce the complete official XML from independently released declaration
values plus explicit target mechanics. It needs no Package graph, obligation
rows, completeness receipt, calculation evidence, Tax Model, Gate 4, SQL,
source document or provider input.

The smallest production-quality inactive contract is:

```text
Gate5DeclarationSemanticInputRuntimeFactory.create
  validates Package-bound RELEASE once upstream
  -> thin released projection input

thin released projection input
+ target mechanics { electronic_file_id }
+ immutable consumer-first Projection Definition
  -> existing Gate5FullTargetXmlTreeProjector
  -> existing serializer
  -> existing official XSD validator
```

The current `project(semantic_input=...)` route remains authoritative and
unchanged. No E2E shadow, cutover, persistence or product caller was added.

Machine-readable evidence is in the
[receipt](./BROKER_REPORTS_GATE5_CONSUMER_FIRST_PROJECTION_G5_39AG.receipt.safe.json)
and the
[demand matrix](./BROKER_REPORTS_GATE5_CONSUMER_FIRST_PROJECTION_G5_39AG.matrix.safe.json).

## 1. Projection consumer contract

The new inactive projector entrypoint receives exactly two objects.

Released projection input:

```text
schema_version
status = DECLARATION_VALUES_RELEASED
value_contract
declaration_values
semantic_value_sha256
release_receipt_sha256
projection_input_sha256
```

Target mechanics input:

```text
schema_version
status = TARGET_MECHANICS_READY
electronic_file_id
target_mechanics_sha256
```

The upstream `prepare_released_projection_input(package, released)` method is
on the existing release owner. It first revalidates the complete released
envelope against the same Package and only then removes audit/completeness
payloads. The projector validates the thin value contract but cannot read or
recover the Package.

The thin input contains no `package`, `semantic_input_sha256`, component
snapshot, source binding, methodology trace, obligation/domain state,
completeness payload or calculation evidence.

## 2. Released-value to target demand matrix

The full accounting is recorded row-by-row in the safe matrix.

| Measure | Result |
| --- | ---: |
| released value leaves | 46 |
| leaves with current target demand | 44 |
| leaves without current target demand | 2 |
| target mapping occurrences / IDs | 49 / 49 |
| declaration-value-dependent mapping occurrences | 44 |
| target-instance-mechanic mappings | 1 |
| immutable target-constant mappings | 4 |
| unjustified dependencies | 0 |

The two currently unconsumed leaves are `signer.identity` and
`russian_source_income[].source_party.party_kind`. They remain valid
declaration values; the current XML subtree simply has no target demand for
them.

The counts are intentionally not treated as 1:1. `budget_dispositions[].kind`
drives payable/refundable target shaping without its own XML mapping, while the
same released `amount` supplies two official target attributes after shaping.

## 3. Target mechanics contract

Per-instance target mechanics contain only `electronic_file_id`.

The immutable Projection Definition owns:

- program version, electronic format version, KND and period code constants;
- official hierarchy, node and attribute order;
- released enum to official code mappings;
- collection iteration in released order;
- `released_kind_to_dual_target_amounts_v0` shaping;
- `windows-1251` serialization and the official XSD pin.

Budget shaping reads the already released `kind`; it does not decide whether
tax is payable or refundable. In the proven profile, `additional_payment`
places the released amount in `ПодлУпл` and represents the other official
amount as zero in `ПодлВозв`.

Changing only the electronic file ID preserved `semantic_value_sha256`, changed
only the `file-id` mapping value hash, and kept both XML instances XSD-valid.

## 4. Projection Definition version decision

A new immutable resource was required because the source contract and source
paths changed. The legacy resource remains byte-for-byte immutable.

```text
legacy:
  ru_3ndfl_2025_full_target_supplied_case
  2026-08-11.0-proof

consumer-first:
  ru_3ndfl_2025_consumer_first_supplied_case
  2026-08-12.0-consumer-first-proof
  sha256 a0cadf748bfc4bd689be586a0a9b88cf783ee3afbba200a744bb1b01d81c46f8
```

The new resource intentionally contains no `required_domain_states` or
`semantic_coverage`. Those are upstream release/audit concerns. Its target
tree, mapping IDs, target paths, transforms, constants, order, target metadata
and XSD are equivalent to the legacy definition.

## 5. Implementation diff

Only justified owners changed:

- existing Semantic Input/release runtime: one factory-owned thin handoff and
  its strict validator;
- existing full-target projection runtime: one inactive `project_released`
  method, lazy consumer-definition authority and bounded target shaping;
- one new hash-pinned Projection Definition resource;
- focused contract tests and one closed-world bundle assertion;
- bundle resource manifest and mechanically regenerated Gate 1 bundle;
- two existing exact Gate 1 bundle hash guards.

The consumer resource is resolved lazily. A missing or corrupted inactive
resource therefore fails the new call but does not prevent the legacy runtime
from projecting successfully.

## 6. Semantic-valid pressure cases

| Profile | Evidence | Terminal |
| --- | --- | --- |
| payable, one allocation | fresh real Package assembly through current E2E factories | proven |
| alternate electronic file identity | same released values, explicit target mechanics | mechanics isolation proven |
| refund | no honest released Package fixture | `PROFILE_NOT_YET_PROVEN`, fails closed |
| balanced | no honest released Package fixture | `PROFILE_NOT_YET_PROVEN`, fails closed |
| multiple budget allocations | no honest released Package fixture | `PROFILE_NOT_YET_PROVEN`, fails closed |
| empty budget allocations | rejected by the released value contract | `PROFILE_NOT_YET_PROVEN`, fails closed |

No rich-payload mutation was promoted as a semantic-valid case. XSD-only
success from older probes is not used as evidence.

## 7. Legacy/new equivalence evidence

For the same semantic-valid Package, same target mechanics and same XSD:

| Check | Result |
| --- | --- |
| mapping identities and order | 49/49 equal |
| target paths | 49/49 equal |
| target value hashes | 49/49 equal |
| legacy official XSD | pass |
| consumer-first official XSD | pass |
| XML bytes | exactly equal, 1,112 bytes |
| XML SHA-256 | `07d2a96d89776d71877bdd1f30ce142a4c6b6f905e09d3e8bcfe238195a8ef2a` |

The consumer-first mapping proof hash is
`aacc4eef1d026d38920bd9284dff6f71de9e3ad704beb7abc466574c8a1576bc`.

## 8. Negative and audit-isolation proof

- Removing released `allowable_expenses` fails before target creation with
  `gate5_consumer_first_released_values_invalid` bound to the existing required
  value terminal. There is no Package/rich/default-zero fallback.
- Refund and balanced kinds fail with
  `gate5_consumer_first_projection_profile_unproven`.
- Two budget allocations fail with the same explicit unproven-profile terminal.
- Empty collections cannot pass the strict released value contract.
- The projector method has no Package, obligation, completeness, Tax Model,
  Gate 4, SQL, store or provider read.
- The representation receipt retains only the released semantic value,
  authorization identity, Projection Definition, target mechanics, mapping,
  XSD and XML identities. It does not copy the 25 obligation rows or evidence
  manifest.

The irreversible boundary for the tests is target XML creation/publication.
Every negative case raises before a result exists; no persistence/publication
path was introduced.

## 9. Legacy invariance and replay

Windows PowerShell, service cwd
`services/broker-reports-gate1-proof`:

| Surface | Result |
| --- | --- |
| focused consumer-first contract | `8 passed` |
| legacy projection, legacy E2E and bundle group | `28 passed`, 5 pre-existing SWIG warnings |
| every `test_broker_reports_gate5*.py` | `407 passed` |
| architecture, product, bundle, atomic release and delivery verifier | `54 passed`, 6 pre-existing warnings |
| targeted Ruff | pass |
| JSON parsing and immutable hash pins | pass |
| `git diff --check` | pass |

The current product path still calls only legacy `project`. No
`project_released` E2E/product caller exists. The regenerated Gate 1 bundle is
the closed-world mirror and includes the new resource; its SHA-256 is
`0bdea62e971e3e39e068785fb956a1ae47882fc2d2144fd479d16c16fc9d68ed`.

## 10. Stable identities

The proof keeps separate identities:

| Identity | SHA-256 |
| --- | --- |
| declaration business values | `83484fd29f261888d4c1fd466672ba52ace4653a46d89ed445ac574a47258090` |
| release authorization in this replay | `7a4acefca04467bb19accc3b2cb1c7a8b9b8974cf9b5f4b586c7cb0d417487c4` |
| thin projection input | `dc7f413b943feae52f52d5bfd76793b354921524345c611afbdb2db06d04c616` |
| target mechanics | `14fc6d6d639280394f7d0783cbfcec981637b230c6ed27ed477d6cd13856c359` |
| Projection Definition | `a0cadf748bfc4bd689be586a0a9b88cf783ee3afbba200a744bb1b01d81c46f8` |
| XML instance | `07d2a96d89776d71877bdd1f30ce142a4c6b6f905e09d3e8bcfe238195a8ef2a` |

The release receipt is run/audit-bound and may change for an equivalent fresh
Package replay. It is not substituted for semantic identity.

## 11. KISS audit

The implementation deliberately did not create a second projection engine,
target registry, plugin system, mapper DSL, compatibility framework, target
graph, persistence model, E2E parity route or product feature flag. The same
tree projector, serializer and XSD validator are reused.

No Tax Model, methodology, Resolved Package, Gate 3, Gate 4, product/public
contract, ArtifactStore, ACL or user-isolation behavior changed.

## 12. Terminal and stop

The core three-contract hypothesis is proven for the one honest bounded
profile:

```text
RELEASED DECLARATION VALUES
+ EXPLICIT TARGET MECHANICS
+ VERSIONED PROJECTION DEFINITION
-> COMPLETE OFFICIAL REPRESENTATION
```

The stronger all-profile terminal is not claimed because no semantic-valid
refund, balanced, multiple-allocation or empty-allocation Package authority is
available. The honest terminal is therefore:

```text
CONSUMER_FIRST_PROJECTION_CORE_PROVEN
PROFILE_BOUNDARIES_UNPROVEN = [
  refund_available,
  balanced,
  multiple_budget_allocations,
  empty_budget_allocations
]
```

The observation, hypothesis, iterations and terminal were added to
[GitHub issue #278](https://github.com/Kwentin3/corp-openweb-ui/issues/278#issuecomment-5270165084).
G5.39AH is not started. Product activation, persistence, cutover, commit, push
and PR remain outside this GOAL.
