# Broker Reports Gate 2 Managed Financial Domain — Goal 2C Safe Evidence Reconciliation

Date: 2026-07-26

Status: `SUPERSEDED_INCORRECT_HASH_BOUNDARY`

Current authority: false

Superseded by: `GOAL_2D_PORTABLE_GIT_BLOB_EVIDENCE`

Base revision: `4bdca5f1bc70ccebe55791d47aa10791a28399b2`

Branch:
`codex/broker-reports-gate2-domain-goal2c-reconcile-safe-evidence`

## 1. Supersession outcome

GOAL 2C was based on an incorrect byte boundary. It compared the original,
portable Git-blob SHA-256 values to files expanded to CRLF by the Windows
checkout under `core.autocrlf=true`. The four differences were newline
conversion, not repository drift.

The original GOAL 2 hashes were correct. The four values introduced below by
GOAL 2C are Windows working-tree hashes and are not current authority.
GOAL 2D restores Git-blob hashes and replaces the regression check with a
checkout-independent Git-object check.

The Financial Semantic Pack content, canonical 9,404-byte semantic material,
integrity hash, admitted type set, consumer contract, and target authority
boundary never changed.

## 2. Superseded working-tree values

| Deliverable | Superseded Windows CRLF SHA-256 |
|---|---|
| Financial Semantic Pack | `9538ccb8f2111efa24e25d1b7b10145ccff8ca4e3c655cdc6d71b916d926c3fd` |
| Financial Semantic Pack schema | `833b1d15b0e383ee80220ba5f347b4009d150ff8ce19336e17aff3c805d70385` |
| Financial Semantic Pack contract | `a34f3ab1db3f9cbfb92541b5045b5425b5547dec52f17e08d97525e49490305f` |
| Financial Semantic Pack tests after guard addition | `62ff2dad6bfade42e9f0c553a72f55ae9b5ac67f70f24f3f717607ea978db4a4` |

The superseded Windows working-tree GOAL 2 receipt SHA-256 was
`31b8a9709f39d5014ccadcf9a0ff13fabad923488ff3d82ed339318d998bd3cf`.

## 3. Incorrect regression boundary

`test_goal2_safe_receipt_hashes_current_deliverables` loads the GOAL 2 safe
receipt, reads each declared repository-relative deliverable, recomputes its
SHA-256 from working-tree bytes, and reports every mismatch. On Windows with
Git newline conversion this is not equivalent to the repository blob and is
therefore superseded.

GOAL 2C changed no:

- Semantic Pack meaning, schema, version, or integrity hash;
- runtime Python behavior;
- OpenWebUI asset or configuration;
- provider policy or model admission;
- stage or production state;
- customer/private data handling.

## 4. Historical verification, not current authority

Explicit PowerShell cwd:
`services/broker-reports-gate1-proof`; test ENV: none.

- focused Pack/evidence tests: `9 passed in 0.36s`;
- full Broker Reports suite:
  `1537 passed, 20 skipped, 5 warnings in 114.32s`;
- repository privacy guard: `3 passed in 0.79s`;
- targeted Ruff: passed;
- targeted compileall: passed;
- `git diff --check`: passed;
- GOAL 2 working-tree hash mismatches after CRLF-specific replacement: 0;
- GOAL 2 report contains exact current receipt hash: yes;
- provider/customer/model calls: 0;
- tokens/cost: 0 / USD 0;
- fallback/repair: 0 / 0;
- stage/production mutations: 0 / 0.

These results were real test executions, but the hash conclusion used the
wrong byte boundary and cannot support acceptance.

## 5. Historical deliverables

1. reconciled GOAL 2 report;
2. reconciled GOAL 2 safe receipt;
3. Financial Semantic Pack test with current-hash guard;
4. this corrective report;
5. repository-safe corrective receipt:
   [`BROKER_REPORTS_GATE2_DOMAIN_GOAL2C_SAFE_EVIDENCE_RECONCILIATION.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL2C_SAFE_EVIDENCE_RECONCILIATION.receipt.safe.json)
   - SHA-256:
     `4fe2cb6ca254aabd6394f730e963b64a3bc2c54d31c6ce0d105676d89e0aae4d`

## 6. Supersession markers

```text
GOAL2C_STATUS: SUPERSEDED_NOT_AUTHORITY
PORTABLE_HASH_BOUNDARY: FAILED
SEMANTIC_AUTHORITY_CHANGE: ZERO
STAGE_PRODUCTION_CHANGE: ZERO
NEXT_PERMITTED_GOAL: GOAL_2D_CORRECTION_REQUIRED_BEFORE_GOAL_3
```
