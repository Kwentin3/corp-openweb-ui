# Broker Reports Gate 5 Supplemental Fact Discovery v0

Status: `EXPERIMENTAL_G5_5_CONTRACT`

Goal status: `G5.5_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Purpose

This contract defines one minimal read-only seam that restores eligible
Supplemental Facts from trusted case context before invoking the existing
G5.4 combined requirement check.

```text
external requirement + trusted ArtifactAccessContext
-> current ArtifactResolver case catalog
-> eligible G5.3 supplemental refs selected internally
-> unchanged G5.4 check
-> satisfied / missing with tagged provenance
```

The caller does not provide or retain opaque supplemental artifact refs.

## Ownership

| Concern | Owner |
| --- | --- |
| access-scoped case artifact metadata | unchanged `ArtifactResolver.catalog_case` |
| supplemental payload/access/lifecycle validation | unchanged `Gate5SupplementalFactRuntime.get` through G5.4 |
| Financial Case + Supplemental Fact decision | unchanged `Gate5CombinedRequirementCheckRuntime.check` |
| internal discovery and delegation | `Gate5SupplementalFactDiscoveryRuntimeFactory.create` |

No store, resolver, Gate 4 or G5.3 persistence contract is changed.

## Contract input

```python
runtime.check(
    methodology=<broker_reports_gate5_combined_requirements_v0>,
    context=<trusted ArtifactAccessContext>,
)
```

There is no `supplemental_fact_refs`, `user_id`, `case_id`, workspace or run
authority parameter. Identity comes only from the trusted context.

The methodology and result schemas remain the exact G5.4 schemas. G5.5 does
not create a second requirement or result language.

## Discovery rule

For one check the runtime:

1. calls `ArtifactResolver.catalog_case(context)`;
2. retains only records with the exact G5.3 supplemental artifact type;
3. retains only records whose `normalization_run_id` equals the trusted
   context run;
4. passes those internally discovered opaque refs to the unchanged G5.4
   runtime;
5. lets G5.4/G5.3 resolve every selected ref through the existing access,
   lifecycle, artifact-type and payload validation boundary.

The runtime never reads payloads from catalog metadata and does not implement
a generic filter/query API.

## Trusted scope and run binding

`ArtifactResolver.catalog_case` derives user, case and workspace scope from
the trusted context. Foreign user, case or workspace records are not selected.

G5.3 currently binds each Supplemental Fact to one `normalization_run_id` and
its payload validation requires the same trusted context. Therefore only
same-run facts are eligible in G5.5. A fact from another run of the same case
remains unavailable and must not be silently rebound.

A new runtime instance with the same trusted run context is sufficient for
the representative reopen proof. Cross-run rebinding/migration is outside
G5.5 and remains an explicit lifecycle limitation.

## Contract output

The result is the unchanged
`broker_reports_gate5_combined_requirement_check_result_v0` output.

Supplemental satisfaction retains the G5.4 tagged source:

```json
{
  "status": "satisfied",
  "source": {
    "source_kind": "supplemental_fact",
    "supplemental_fact_ref": "art_<opaque>",
    "value": {
      "kind": "money",
      "amount": "70000.00",
      "currency": "RUB"
    },
    "scope_binding": {},
    "provenance": {}
  }
}
```

No eligible fact leaves the G5.4 result `missing` with `source: null`.

## Fail-closed boundary

- catalog scope comes only from `ArtifactAccessContext`;
- foreign scope is excluded by the existing case catalog owner;
- another run is not eligible;
- discovered records are metadata only until G5.3 resolves them;
- corrupt, blocked, expired, purged or otherwise invalid selected facts fail
  through existing G5.3/ArtifactResolver checks;
- multiple eligible matching facts retain the existing G5.4 ambiguous error;
- Gate 4 freshness and read errors pass through G5.4/G5.2 unchanged.

## Representative acceptance

The real-boundary proof must show:

1. a Gate 4 disposal lacks `acquisition_cost`;
2. G5.3 persists `70000.00 RUB` in the trusted case/run;
3. a new store/runtime instance receives only methodology and trusted context;
4. no opaque supplemental refs are supplied by the caller;
5. the runtime discovers the persisted fact and G5.4 returns `satisfied`;
6. value, scope binding and provenance are preserved;
7. without an eligible same-scope fact the result is `missing`;
8. foreign user/case and other-run facts do not satisfy the requirement;
9. Gate 4 before and after is structurally equal;
10. G5.5 creates no persistence state, index, table or registry.

## KISS and stop condition

G5.5 may add one read-only factory-backed adapter, one closed contract and
focused proof tests. It must not add a registry, DB/table/index, Tax Case,
generic query/filter API, conflict resolver, workflow, relation layer,
semantic matching, cross-run framework or subsequent Gate 5 slice.

The representative exact-runtime proof passed, so `G5.5_CLOSED`. This
contract authorizes no subsequent slice.
