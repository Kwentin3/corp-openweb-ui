# Broker Reports Gate 2 Managed Financial Domain — Goal 2C Safe Evidence Reconciliation

Date: 2026-07-26

Status: `IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`

Base revision: `4bdca5f1bc70ccebe55791d47aa10791a28399b2`

Branch:
`codex/broker-reports-gate2-domain-goal2c-reconcile-safe-evidence`

## 1. Outcome

A fresh post-merge repository pass found a blocking evidence-integrity defect
in GOAL 2: its report and safe receipt still declared the four deliverable
SHA-256 values calculated before the final semantic-definition correction.
All four merged files therefore differed from their claimed hashes.

GOAL 2C:

- replaces all four stale claims with hashes of the merged bytes;
- updates the GOAL 2 report's receipt hash;
- records why reconciliation was required;
- adds a regression test that recomputes every receipt-declared deliverable
  hash.

The Financial Semantic Pack content, canonical 9,404-byte semantic material,
integrity hash, admitted type set, consumer contract, and target authority
boundary are unchanged.

## 2. Exact correction

| Deliverable | Correct SHA-256 |
|---|---|
| Financial Semantic Pack | `9538ccb8f2111efa24e25d1b7b10145ccff8ca4e3c655cdc6d71b916d926c3fd` |
| Financial Semantic Pack schema | `833b1d15b0e383ee80220ba5f347b4009d150ff8ce19336e17aff3c805d70385` |
| Financial Semantic Pack contract | `a34f3ab1db3f9cbfb92541b5045b5425b5547dec52f17e08d97525e49490305f` |
| Financial Semantic Pack tests after guard addition | `62ff2dad6bfade42e9f0c553a72f55ae9b5ac67f70f24f3f717607ea978db4a4` |

The reconciled GOAL 2 receipt SHA-256 is
`31b8a9709f39d5014ccadcf9a0ff13fabad923488ff3d82ed339318d998bd3cf`.

## 3. Regression boundary

`test_goal2_safe_receipt_hashes_current_deliverables` loads the GOAL 2 safe
receipt, reads each declared repository-relative deliverable, recomputes its
SHA-256 from bytes, and reports every mismatch. It does not accept a report
claim as proof.

This is an evidence-only corrective GOAL. It changes no:

- Semantic Pack meaning, schema, version, or integrity hash;
- runtime Python behavior;
- OpenWebUI asset or configuration;
- provider policy or model admission;
- stage or production state;
- customer/private data handling.

## 4. Verification

Explicit PowerShell cwd:
`services/broker-reports-gate1-proof`; test ENV: none.

- focused Pack/evidence tests: `9 passed in 0.36s`;
- full Broker Reports suite:
  `1537 passed, 20 skipped, 5 warnings in 114.32s`;
- repository privacy guard: `3 passed in 0.79s`;
- targeted Ruff: passed;
- targeted compileall: passed;
- `git diff --check`: passed;
- GOAL 2 declared deliverable hash mismatches: 0;
- GOAL 2 report contains exact current receipt hash: yes;
- provider/customer/model calls: 0;
- tokens/cost: 0 / USD 0;
- fallback/repair: 0 / 0;
- stage/production mutations: 0 / 0.

## 5. Deliverables

1. reconciled GOAL 2 report;
2. reconciled GOAL 2 safe receipt;
3. Financial Semantic Pack test with current-hash guard;
4. this corrective report;
5. repository-safe corrective receipt:
   [`BROKER_REPORTS_GATE2_DOMAIN_GOAL2C_SAFE_EVIDENCE_RECONCILIATION.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL2C_SAFE_EVIDENCE_RECONCILIATION.receipt.safe.json)
   - SHA-256:
     `4fe2cb6ca254aabd6394f730e963b64a3bc2c54d31c6ce0d105676d89e0aae4d`

## 6. Acceptance markers

```text
STALE_GOAL2_DELIVERABLE_HASHES: ZERO
CURRENT_HASH_GUARD: ENFORCED
SEMANTIC_AUTHORITY_CHANGE: ZERO
STAGE_PRODUCTION_CHANGE: ZERO
NEXT_PERMITTED_GOAL: GOAL_3_AFTER_GOAL_2C_REVIEW_ACCEPTANCE_AND_MERGE
```
