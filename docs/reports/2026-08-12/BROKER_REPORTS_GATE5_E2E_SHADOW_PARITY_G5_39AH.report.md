# G5.39AH - End-to-End Shadow Parity

Verified: 2026-08-12

Mode: autonomous research plus test-first inactive integration

Terminal: `E2E_SHADOW_PARITY_PROVEN`

Supported profile: `payable_one_allocation`

## Decision

The consumer-first projection can run as a non-authoritative shadow inside the
existing real E2E owner. Both target paths consume one already assembled
Resolved Package boundary; Gate 4, Tax Models and Package assembly each run
once. The payable/one-allocation result is equal under the G5.39AG contract:
49/49 mapping identities, target paths and target value hashes, official XSD
conformance, XML binding and XML bytes.

Legacy remains the only product authority. The shadow candidate is discarded,
is not returned to the user, is not persisted and cannot be downloaded.

Machine-readable aggregate evidence is in the
[safe receipt](./BROKER_REPORTS_GATE5_E2E_SHADOW_PARITY_G5_39AH.receipt.safe.json).

## 1. Minimal seam

The existing `Gate5EndToEndFullTargetXmlRuntime` gained one optional private
receipt sink. Normal callers omit it and receive the exact legacy result shape:

```text
status
xml_bytes
semantic_input
receipt
```

When the control sink is supplied, the runtime first completes and validates
that legacy result. It then derives the already proven release from the same
Package, invokes the existing consumer-first projector once and emits only a
privacy-safe parity receipt to the control sink.

The product owner does not pass the sink and contains no `project_released`
call. No public response, persistence or download contract changed.

## 2. Same-Package and recomputation proof

The frozen control run bound all three Package identities to:

```text
bb9ffd405cfc5eab18e10083c02fb2c8d16cc20788cc0a9d09387a412ed4f6c3
```

| Observed owner call | Count |
| --- | ---: |
| Gate 4 rebuild | 1 |
| Gate 5 Tax Model tail | 1 |
| Resolved Package assembly | 1 |
| legacy projection | 1 |
| consumer-first projection | 1 |
| provider calls | 2 |

The two provider calls are the unchanged Gate 3 labeling and role-labeling
calls. Shadow adds zero provider calls. The existing full E2E invokes its source
helper once in `run` and once at the validated-Gate-3 boundary; the shadow
evaluator itself contains no source read and adds zero source calls.

The semantic owner has two public `compile` calls after the shared Package
boundary: one for the legacy branch and one for the release-candidate branch.
This is downstream branch work, not a second Gate 4, Tax Model or Package build.

## 3. Parity evidence

| Check | Result |
| --- | --- |
| same Resolved Package | pass |
| mapping occurrences | 49 legacy / 49 shadow |
| mapping ID, target path and value-hash projection | equal |
| official XSD conformance proof | equal |
| XML binding | equal |
| XML bytes | equal, 1,112 bytes |
| XML SHA-256 | `07d2a96d89776d71877bdd1f30ce142a4c6b6f905e09d3e8bcfe238195a8ef2a` |

Both mapping projections have SHA-256
`b683a24528920a1a78a191906fa9946d7ce200c1663ad70ecb0ed927b69eee09`.

## 4. Failure isolation, persistence and rollback

Fault injection after a real consumer projection proved that an XML mismatch
produces `E2E_SHADOW_PARITY_FAILED`. A consumer profile rejection produces
`PROFILE_NOT_PROVEN`. In both cases:

- the legacy E2E terminal and official XML remain unchanged;
- the candidate is discarded;
- no candidate result reaches the returned legacy object;
- the persisted artifact-type multiset equals the legacy-only baseline;
- no shadow artifact type exists.

The shadow-enabled proof run had the same 26 ordinary upstream artifact records
across 25 types as the legacy baseline. There is no new ArtifactStore model,
write, retention rule, download surface or ACL path.

Rollback is therefore only to stop supplying the private receipt sink. It
requires no data migration, tax replay or cleanup of shadow artifacts.

## 5. Profile boundary

Only `payable_one_allocation`, proven in G5.39AG, participates in the successful
shadow. Refund, balanced, multiple-allocation and empty-allocation profiles are
not promoted for AH. The consumer projector continues to fail those boundaries
closed; the E2E shadow translates the explicit profile rejection to
`PROFILE_NOT_PROVEN` while leaving legacy authoritative.

## 6. KISS audit

The change reuses the existing E2E, release, projection, serializer and XSD
owners. It adds no second pipeline, projection engine, schema registry, graph,
plugin system, feature-flag framework, SQL authority, persistence artifact or
product caller.

The Gate 1 bundle was mechanically regenerated as the closed-world mirror. Its
SHA-256 is
`348266f250fa19fb86270f14cad060ecd1a65916d01508aa279d679839ae899d`.

## 7. Replay

Windows PowerShell, service cwd
`services/broker-reports-gate1-proof`:

| Surface | Result |
| --- | --- |
| focused AH | `4 passed` |
| legacy E2E + AG + AH focused group | `20 passed` |
| projection/E2E/bundle targeted group | `25 passed`, 5 pre-existing SWIG warnings |
| every `test_broker_reports_gate5_*.py` | `411 passed` |
| product, persistence, download, ACL, bundle, atomic release and architecture | `96 passed`, 6 pre-existing warnings |
| targeted Ruff | pass |

The first broad replay correctly detected one stale generated bundle module
after the source edit (`95 passed, 1 failed`). The maintained bundle builder was
run, the two existing exact hash guards were updated, and all relevant replay
then passed.

## 8. Terminal and stop

```text
E2E_SHADOW_PARITY_PROVEN
SUPPORTED_PROFILE = payable_one_allocation
LEGACY_PRODUCT_AUTHORITY = true
```

The stronger terminal applies to the currently supported shadow profile, not
to unsupported tax profiles. G5.39AI is the next allowed boundary and was not
started. No cutover, product activation, persistence change, commit, push or PR
was performed.
