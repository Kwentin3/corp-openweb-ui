# Broker Reports Gate 2 Managed Financial Domain — Goal 1 Consumer Contract

Date: 2026-07-26

Status: `IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`

Base revision: `7e7897cd0d8e7e5918b1836865202d97e7fd6071`

Branch: `codex/broker-reports-gate2-domain-goal1-managed-domain-contract`

## 1. Outcome

GOAL 1 defines a stable, versioned Gate 2 consumer boundary for Gate 3:

- normative contract:
  `broker_reports_managed_financial_domain_contract_v1`;
- strict JSON Schema 2020-12:
  `urn:broker-reports:contracts:managed-financial-domain:v1`;
- eight first-class DTO schemas for typed records, unclassified records,
  snapshots, catalogs, coverage, provenance, query requests, and query
  responses;
- deterministic exact-match query filters over type, document, period,
  currency, and record kind;
- immutable-snapshot pagination with a hard page limit from 1 through 200;
- explicit separation of query-result completeness from source-coverage
  completeness.

The contract is repository normative but not live activated. Transport,
persistence, OpenWebUI assets, Semantic Pack contents, model qualification,
and production release remain later GOALs.

## 2. Consumer boundary

Gate 3 can discover:

- which types are declared by the pinned Semantic Pack;
- which types are populated in the selected snapshot;
- which documents, periods, and currencies occur in materialized records;
- typed and unclassified record totals;
- uncovered source-ref totals and optional refs;
- opaque provenance refs and expanded provenance after server-side access
  checks.

Gate 3 cannot read the Artifact Store directly. The domain server owns access
checks, private resolution, deterministic filtering, continuation tokens, and
completeness statements.

## 3. Records and authority

A typed record is valid only when it is bound to:

- the snapshot's exact Semantic Pack identity;
- one stable `input_type_id`;
- retained source-bound role values;
- source dimensions and provenance;
- a canonical record hash.

An unclassified record is first-class data with retained source values,
dimensions, reason codes, provenance, and a canonical hash. It has no
`input_type_id` and cannot be silently upcast.

Provider output is a proposal, not a record authority. The earlier
12-candidate Fact Registry research is not promoted by this GOAL. Current
runtime/production authority is unchanged.

## 4. Coverage and completeness

Coverage has exactly four terminal source outcomes:

- `typed`;
- `unclassified`;
- `no_financial_input`;
- `unsupported`.

`no_financial_input` and `unsupported` are coverage outcomes, not records.
Complete terminal ownership requires exact declared-ref accounting, zero
uncovered refs, zero duplicates, and zero ownership conflicts.

A continued page is valid but not a complete query. The final page is complete
only when its cumulative returned count equals the exact matching record
count and no continuation token remains. A query may be complete over
materialized records while source coverage remains partial; both statuses are
always visible.

The contract forbids silent omission caused by an internal cap. Unsafe token,
snapshot, access, retention, or integrity conditions fail closed.

## 5. Explicit non-goals

This diff adds no:

- production/runtime behavior;
- API transport or persistence;
- Semantic Pack type definitions;
- financial-language classifier, predicate, or regex;
- provider, customer, source-model, or domain-model call;
- fallback or repair;
- stage mutation;
- tax, declaration, ledger, cost-basis, P/L, netting, or currency-conversion
  methodology.

## 6. Deliverables

1. `docs/stage2/contracts/BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md`
   - SHA-256:
     `8edb4a49e1d12cda03ac31ccd3b633e43d60806d28333faff01f06ac4d9f74d9`
2. `docs/stage2/contracts/BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.schema.json`
   - file SHA-256:
     `1a522ef75b38fbb6c827fc4de321273ccf3b1ec7c16a6a550c8f3ae35e6113bd`
   - canonical JSON SHA-256:
     `0e4255441f82c0b323022695c2ec603dea842ebe64d0eef5d95064e92d0af3c9`
3. `services/broker-reports-gate1-proof/tests/test_broker_reports_managed_financial_domain_contract.py`
   - SHA-256:
     `ae0a3b787d43f1e93ba96c2ad619a3360bad97a62bccac2520f5b79d7fcf566c`
4. repository-safe receipt:
   [`BROKER_REPORTS_GATE2_DOMAIN_GOAL1_MANAGED_FINANCIAL_DOMAIN_CONTRACT.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL1_MANAGED_FINANCIAL_DOMAIN_CONTRACT.receipt.safe.json)
   - SHA-256:
     `95eafd07913547849a570a86f6914151d4ee6be3f9a1127099a43e2b59ad0dc2`

## 7. Fresh review corrections

The first remote PR-head review returned `CHANGES_REQUIRED` with four in-scope
findings:

1. a continued response could contain zero records and make no progress;
2. a blocked response could contain a partial record payload;
3. a response did not self-pin Pack, coverage, effective filters, and page
   limit;
4. canonical hash material was not normative.

The schema now requires positive progress for continued pages and an empty
payload for blocked pages. Query responses self-pin the missing identity and
query fields. Canonical integrity material is fixed for records, record sets,
catalog, coverage, provenance lineage, and query fingerprints.

The corrected schema probe accepted 10 positive DTO cases and rejected 9
negative cases, including all four review defect paths.

## 8. Verification

Shell and cwd were explicit PowerShell executions under
`services/broker-reports-gate1-proof`; no test ENV was required.

- contract tests: `6 passed in 0.40s`;
- focused Registry/decision/materialization/context/successor tests:
  `120 passed in 1.55s`;
- full Broker Reports suite:
  `1528 passed, 20 skipped, 5 warnings in 111.50s`;
- JSON Schema instance probe:
  10 positive DTO cases passed and 9 negative invariant violations were
  rejected;
- JSON Schema meta-validation: passed;
- targeted Ruff: passed;
- targeted compileall: passed;
- repository privacy guard: `3 passed in 0.77s`;
- customer values, documents, raw provider output, secrets, and private paths
  in deliverables: zero.

One earlier focused command incorrectly used a Unix backslash as PowerShell
continuation and caused pytest to collect the `D:\` drive. That run was
invalid, made no repository mutation, and is excluded. The exact PowerShell
path-array rerun above is the accepted focused result.

## 9. Test integrity

The new tests read the real committed contract and schema without mocks. They
assert closed DTOs, Semantic Pack and provenance binding, first-class
unclassified data, terminal coverage, exact query filters, deterministic
ordering, bounded pagination, and terminal completeness states.

Test state is isolated and read-only; each test reloads the repository files.
There is no handler, asynchronous protocol, irreversible side effect, external
service, or environment-dependent outcome in this GOAL.

## 10. Acceptance markers

```text
FINANCIAL_DOMAIN_CONTRACT: VERSIONED
GATE3_CONSUMER_BOUNDARY: EXPLICIT
QUERY_COMPLETENESS: DEFINED
UNCLASSIFIED: FIRST_CLASS_DATA
PRODUCTION_CHANGE: ZERO
STAGE_MUTATIONS: ZERO
NEXT_PERMITTED_GOAL: GOAL_2_AFTER_GOAL_1_REVIEW_ACCEPTANCE_AND_MERGE
```
