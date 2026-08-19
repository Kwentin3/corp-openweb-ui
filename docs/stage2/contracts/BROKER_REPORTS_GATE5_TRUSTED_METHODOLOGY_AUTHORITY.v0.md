# Broker Reports Gate 5 Trusted Methodology Authority v0

Status: `EXPERIMENTAL_G5_8_CONTRACT`

Goal status: `G5.8_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Purpose

This contract places one trusted system-owned methodology resolution boundary
before the unchanged G5.7 calculator.

```text
repository-versioned hash-pinned methodology resource
-> exact identity/version resolution
-> unchanged G5.7 calculation boundary
-> authority-bound calculation result
```

It distinguishes a reproducible trusted methodology from reproducible
caller-supplied JSON. It does not define methodology authoring, publication,
effective-date selection or lifecycle management.

## Research finding

The repository already has the required minimal pattern in the Gate 3
Financial Label Dictionary and Role Pack:

- machine-readable package resources;
- stable semantic identity and version;
- a factory-backed loader;
- an exact expected file SHA-256;
- fail-closed resource, identity and hash validation;
- closed-world copy/package tests.

G5.8 reuses this pattern, not those Gate 3 domain owners or their content.

The alternatives were evaluated as follows:

| Candidate | Finding |
| --- | --- |
| repository-versioned package resource | selected; already proven locally, exact, immutable-by-version, closed-world and needs no new persistence |
| OpenWebUI Prompt | has access control and partial history, but its current row content is mutable and it is an LLM prompt surface rather than a Tax Methodology owner |
| OpenWebUI Skill/Tool | access-controlled authoring surfaces, but the pinned version has no complete immutable version/readback lifecycle for this content |
| existing ArtifactStore | immutable per artifact ID and useful for case state, but its authority is authenticated user/case artifacts, not system-published tax meaning |
| new DB/config service | rejected; no current G5.8 requirement justifies new persistence, ACL, CRUD or lifecycle infrastructure |

## Authority owner

The sole G5.8 authority owner is:

```text
Gate5TrustedMethodologyAuthorityFactory.create
```

It loads only resources registered in its closed published-identity map. The
caller cannot supply a resource path, content hash or methodology bytes.

The physical methodology is:

```text
broker_reports_gate1/
  gate5_tax_methodology.ru_ndfl_securities_proof.v0.json
```

The stable identity is:

```text
methodology_id      = ru-ndfl-securities-proof
methodology_version = 2026.0-experimental
```

## Additive G5.13 published identity

G5.13 reuses this same authority instead of adding a second methodology
loader. The closed published map now also binds:

```text
methodology_id      = ru-ndfl-securities-tax-model-proof
methodology_version = 2026.0-experimental
resource            = gate5_tax_methodology.ru_ndfl_securities_tax_model_proof.v0.json
schema              = broker_reports_gate5_securities_disposal_tax_model_methodology_v0
```

Each published entry now carries its expected schema version together with
the resource name and raw-resource SHA-256. This is an additive authority
capability only: the original G5.8 identity and the composed G5.7 calculation
route remain unchanged. The new identity is consumed by the inactive
[`Gate 5 Declaration-Driven Tax Model v0`](./BROKER_REPORTS_GATE5_DECLARATION_DRIVEN_TAX_MODEL.v0.md)
boundary, which owns its structure and behavior validation.

G5.14 appends a new version under the same methodology ID; it does not replace
the G5.13 bytes:

```text
methodology_id      = ru-ndfl-securities-tax-model-proof
methodology_version = 2026.1-experimental
resource            = gate5_tax_methodology.ru_ndfl_securities_operation_tax_model_proof.v0.json
schema              = broker_reports_gate5_securities_disposal_operation_tax_model_methodology_v0
resource_sha256     = 253f6f644eb88c963639833bcef8b169a51e4b8790ab2dcfa22c091b58e30bed
```

The inactive G5.13 `run_operation` path consumes this version for operation
models that deliberately contain no category-completeness claim. G5.14 owns
the later scope binding and aggregation.

G5.22 appends another immutable version under the same authority and
methodology ID:

```text
methodology_id      = ru-ndfl-securities-tax-model-proof
methodology_version = 2026.2-experimental
resource            = gate5_tax_methodology.ru_ndfl_securities_income_group_tax_base_proof.v0.json
schema              = broker_reports_gate5_securities_income_group_tax_base_methodology_v0
resource_sha256     = 56bcc7554c69757623a67497aa728cefc662e8c08a5795dfcb5562da1559bb80
```

It is consumed only by the inactive stable income-group Tax Base behavior.
The earlier `2026.0` and `2026.1` resources remain exact and independently
replayable. G5.8 still owns the sole closed resource/hash resolver; no new
methodology service or mutable catalog was introduced.

The owner binds that tuple to one package resource and one exact raw-resource
SHA-256. The G5.7 canonical projection hash is computed independently from the
decoded JSON and must be repeated exactly in the calculation result.

## Caller reference

The caller supplies one closed reference:

```json
{
  "schema_version": "broker_reports_gate5_trusted_methodology_ref_v0",
  "methodology_id": "ru-ndfl-securities-proof",
  "methodology_version": "2026.0-experimental"
}
```

The reference contains no methodology content, path, hash, behavior, rule,
requirements or bindings. Extra keys fail closed.

The caller may still control:

- which published identity/version it requests;
- the existing trusted `ArtifactAccessContext` for Financial Case and
  Supplemental Fact reads.

The caller can no longer control:

- methodology bytes;
- rule or behavior identity;
- requirement selection or bindings;
- the expected authority/resource hash;
- the resource location.

G5.8 does not choose a methodology automatically by tax period, residency or
effective date.

## Trusted calculation composition

The only composed entrypoint is:

```text
Gate5TrustedMethodologyCalculationRuntimeFactory(...).create()
```

Its runtime performs exactly four operations:

1. validate the closed methodology reference;
2. resolve exact bytes through the trusted authority;
3. pass the resolved projection to unchanged
   `Gate5MethodologyCalculationRuntimeFactory.create`;
4. require the returned G5.7 `methodology_binding` to equal the trusted
   identity/version/canonical projection hash.

It does not read Gate 4, Supplemental Facts, ArtifactStore, SQL, OpenWebUI
tables, source documents or providers directly. G5.7 continues to obtain
inputs only through G5.5.

## Authority-bound output

The wrapper returns:

```json
{
  "schema_version": "broker_reports_gate5_trusted_calculation_result_v0",
  "status": "calculated",
  "authority_binding": {
    "authority_owner": "repository_versioned_package_resource",
    "methodology_id": "ru-ndfl-securities-proof",
    "methodology_version": "2026.0-experimental",
    "resource_sha256": "<exact raw resource SHA-256>",
    "projection_sha256": "<exact canonical G5.7 projection SHA-256>"
  },
  "calculation_result": {
    "schema_version": "broker_reports_gate5_calculation_result_v0",
    "status": "calculated"
  }
}
```

The complete nested G5.7 result is unchanged and retains rule, behavior,
input provenance and outputs.

## Immutability boundary

For the published map, one `(methodology_id, methodology_version)` resolves to
one exact raw-resource hash. Changing only the file causes
`gate5_trusted_methodology_resource_hash_mismatch` before G5.7 runs.

Published identities are append-only by this contract. A new methodology
content version requires a new version identity, resource and hash binding.
Changing both old bytes and their pin would be an explicit reviewed repository
change that violates this contract, not a silent runtime overwrite; historical
calculation results still retain the old canonical projection hash.

This protects against an untrusted runtime caller. It does not claim to defend
against an actor authorized to alter and deploy the application repository.

## Independent methodology evolution

If a future methodology version keeps an already supported G5.7 behavior, it
can be added as a new resource plus new authority identity/hash binding without
changing calculator implementation.

If it names a new behavior, unchanged G5.7 still fails closed until that
behavior is separately reviewed and implemented. G5.8 adds no behavior and
does not weaken this invariant.

## Fail-closed boundary

- malformed or content-bearing caller reference is rejected;
- an unregistered identity/version is rejected as not published;
- a missing resource is rejected;
- raw resource hash mismatch is rejected before JSON use;
- invalid JSON or resource identity mismatch is rejected;
- G5.7 methodology validation and unknown-behavior failures propagate;
- a mismatch between trusted binding and returned G5.7 result is rejected;
- no fallback, implicit default or caller hash is accepted;
- no write boundary exists.

## Representative proof

The trusted resource contains the same experimental G5.7 methodology. With
the existing representative case it resolves:

```text
Financial Case proceeds       = 100.00 RUB
Supplemental acquisition cost = 70.00 RUB
Supplemental transaction fee  = 2.00 RUB
recognized expense            = 72.00 RUB
net result                     = 28.00 RUB
```

A new ArtifactStore and runtime resolve the same trusted resource and return
the identical authority-bound result. Mutating a caller-owned resolved copy
does not affect the next resolution. Gate 4 and Supplemental Facts remain
unchanged.

## KISS and stop condition

G5.8 adds one JSON package resource, one hash-pinned authority/adapter module,
one closed reference/result contract and focused tests.

It adds no DB/table, Artifact registry, Methodology CRUD, approval workflow,
state machine, effective-date selector, Tax Case, Tax Engine, DSL, LLM call,
new behavior or product activation.

The representative authority and replay proof passed, so `G5.8_CLOSED`. No
later Gate 5 slice is authorized by this contract.
