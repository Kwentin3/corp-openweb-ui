# Broker Reports Gate 2 — GOAL 10 Economy Shadow Qualification

Date: 2026-07-26

Branch:
`codex/broker-reports-gate2-domain-goal10-economy-shadow`

Base revision:
`c49bba056d777b65baaa9969390e32454f4d0468`

Implementation revision:
`2b451e7a1168165b1b1902c0c635b7b8bf246715`

Authoring status:
`TERMINAL_REVIEWED_NOT_ACCEPTABLE`

Acceptance status: `NOT_ACCEPTED`

Review status: `NOT_ACCEPTABLE`

Blocking review finding:
`BR-G10-R1_UNSAFE_TYPED_NON_ZERO`

## 1. Outcome

The exact Nano V4 qualification attempt completed once and failed one hard
gate:

```text
MODEL_SAFE_FOR_SHADOW NO
UNSAFE_TYPED 1
DATA_LOSS 0
RECALL 0.5
```

The exact candidate is not safe for shadow admission. GOAL 10 is not
accepted, the branch must not merge, and dependent GOAL 11 is not permitted.

## 2. Implemented boundary

GOAL 10 adds:

1. a normative one-attempt shadow-qualification contract;
2. a separate V4 live qualification harness;
3. policy 1.5 with a qualification-only 6144-token managed-Pack input cap;
4. exact Nano qualification routing for financial evidence;
5. risk-based hard gates and explicit quality measurements;
6. terminal, privacy, policy, and anti-bypass tests.

Production admissions remain empty. The historical V3 Nano and Haiku
receipts were not transferred or rerun.

## 3. Exact qualification identity

- exact model: `gpt-5.4-nano-2026-03-17`;
- provider profile: `openai_gpt`;
- model policy: `1.5.0`;
- model policy SHA-256:
  `04394ee5320d19000639eb73305894e64d104758d2a5f9d824229a3b95d6c53b`;
- workload policy: `1.5.0`;
- workload policy SHA-256:
  `ef1fdf3fd3f9de4a412be130ee476405f3ccc9bf24f9facee2028b4f64fb3d3b`;
- qualification policy SHA-256:
  `4923be403dafb15145a02d36907ad840a7e71213e405455b9d43dbcee4b20a67`;
- authorization identity SHA-256:
  `9560563de99ec80432937187fede47e39b65cca49ab8def6ed7e9f9d4859e651`;
- V4 model input:
  `broker_reports_gate2_financial_evidence_successor_model_input_v4`;
- managed prompt:
  `broker_reports_gate2_financial_evidence_managed_prompt_v1`;
- Semantic Pack SHA-256:
  `ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`;
- managed asset manifest SHA-256:
  `b2d1d51f5894012871d9603b59b2a4dd597c9b83ac4d1b7714bf100468728b59`;
- frozen fixture canonical SHA-256:
  `430bea21d0a36e993bc50184d971f36dfc75a1d2be12bcf5e43fba7436797d66`.

## 4. Preflight

Read-only stage and local preflight passed:

- frozen cases: 12;
- provider calls: 0;
- maximum estimated input tokens: 5393;
- allowed input tokens: 6144;
- estimated input tokens total: 58773;
- estimated maximum cost: USD 0.021354600;
- local domain proof: passed;
- local literal loss: zero;
- local query gaps: zero;
- qualification Action content hash: exact;
- qualification policy hash: exact;
- production admissions: empty.

## 5. Terminal live measurements

- provider calls: 12;
- input tokens: 53047;
- output tokens: 2447;
- actual cost: USD 0.010119990;
- latency observations: 12;
- latency total: 38451 ms;
- latency average: 3204.25 ms;
- latency maximum: 4828 ms;
- typed expected: 4;
- typed observed: 3;
- typed correct: 2;
- typed precision: 0.666667;
- typed recall: 0.5;
- safe under-typing: 2;
- unclassified total: 9;
- unclassified rate: 0.75;
- exact quality matches: 7 of 12;
- exact quality-match rate: 0.583333.

Observed dispositions were three typed and nine unclassified. The model did
not emit the no-financial or unsupported disposition in this attempt.

## 6. Hard-gate result

Passed:

- data loss: 0;
- inventions: 0;
- invalid refs: 0;
- wrong roles: 0;
- duplicate bindings: 0;
- cross-scope bindings: 0;
- ownership gaps: 0;
- canonical/materialization errors: 0;
- product safety proof: passed.

Failed:

- unsafe typed: 1.

The unsafe event was a structurally valid typed classification where the
frozen synthetic reference required unclassified financial input. Two
expected typed cases conservatively became unclassified; those events are
visible as safe under-typing and reduce recall.

## 7. Attempt and retry accounting

Exactly one V4 execution was started. An external command timeout detached
the original process after its atomic checkpoint; the same PID continued to
the terminal checkpoint. No second process or retry was started.

The final full receipt remains outside Git. Its SHA-256 is:

`c371262b9c9d6911b2bb250f441f1f158e5ed1259e93d2d3eefa6df5280f5426`.

Retry, fallback, repair, hidden retry, candidate search, paid tools, and
expensive model calls were all zero.

## 8. Stage lifecycle and rollback

The qualification-only Action was temporarily updated to policy 1.5 after a
zero-call dry-run. The delivery proved:

- repository/live content exact;
- qualification policy exact;
- rollback to the previous Action;
- reapplication of the candidate Action;
- maintained functions unchanged;
- published model inventory unchanged.

Because the qualification failed, the Action was restored to the exact
pre-GOAL stage state:

- content SHA-256:
  `f178b142403e52897d2caf74ad75576162331efa85b0da85d472d8301ad24932`;
- meta SHA-256:
  `6cf2907e2cff2e82a9dc212d27ead39e2bf0f2fe3dc035ba1d2c6e2ccf674bd7`;
- qualification policy SHA-256:
  `901c32f1afe865a835d849285862e8077bbe5f62b7690f63737accbe143a6ebe`;
- active: true;
- global: false.

Total Action mutations were four. Provider and customer calls during Action
delivery and rollback were zero. Production routes were never activated.

## 9. Verification

Run from `services/broker-reports-gate1-proof`:

- focused Goal 10 policy/harness matrix: 98 passed in 20.17s;
- full suite: 1624 passed, 20 skipped, 5 warnings in 173.98s;
- repository privacy guard: 3 passed in 0.83s;
- targeted Ruff: passed;
- targeted `py_compile`: passed;
- `git diff --check`: passed.

The five full-suite warnings are the pre-existing SWIG deprecation warnings;
there are no test failures.

## 10. Privacy

The committed receipt contains only synthetic identifiers, contract/model
identities, aggregates, hashes, tokens, cost, latency, booleans, and terminal
status.

It contains no fixture literal, source-value or source-scope reference,
source group, raw provider output, customer data, secret, token, private
path, or response payload. The full checkpoint remains Git-ignored.

## 11. Deliverables

- [`BROKER_REPORTS_GATE2_MANAGED_FINANCIAL_DOMAIN_SHADOW_QUALIFICATION.v1.md`](../../stage2/contracts/BROKER_REPORTS_GATE2_MANAGED_FINANCIAL_DOMAIN_SHADOW_QUALIFICATION.v1.md)
- [`BROKER_REPORTS_GATE2_DOMAIN_GOAL10_ECONOMY_SHADOW_QUALIFICATION.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL10_ECONOMY_SHADOW_QUALIFICATION.receipt.safe.json)
- `scripts/live_gate2_managed_financial_domain_shadow_qualification.py`
- `tests/test_live_gate2_managed_financial_domain_shadow_qualification.py`

Normative contract Git-blob SHA-256:
`f79eb6e2eb425b42715e3c2ebbd095fb65846647a5b39094440c9974861e72bc`.

Repository-safe receipt Git-blob SHA-256:
`a726b99bcb744eb7e9cab7ede5042c3393a3b7d23aafd6408e1655c063f3adf2`.

## 12. Scope stops

GOAL 10 does not claim:

- model safety for shadow;
- actual-corpus generalization;
- production or stage activation;
- provider admission;
- Gate 3 adequacy;
- release readiness;
- customer acceptance.

Next permitted action:
`EXPLICIT_NEW_CANDIDATE_OR_QUALIFICATION_POLICY_DECISION_REQUIRED`.
