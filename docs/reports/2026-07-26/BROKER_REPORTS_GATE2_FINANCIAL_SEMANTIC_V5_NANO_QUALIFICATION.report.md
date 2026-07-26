# Broker Reports Gate 2 — GOAL 9B Nano V5 Qualification

Date: 2026-07-26

Branch:
`codex/broker-reports-gate2-v5-goal9b-nano-qualification`

Base and qualified repository revision:
`31725ae5a3f57fafb3e399e514bc3813099c521a`

Review target: `EVIDENCE_ONLY`

Product status: `MODEL_NOT_SAFE_FOR_SHADOW`

## Outcome

The one permitted exact Nano V5 qualification attempt completed and failed.
GOAL 10 actual-corpus shadow work is not authorized.

The failure has two separately recorded layers:

1. the live harness rejected all ten semantic results at the exact provider
   execution-metadata gate;
2. offline replay of the same preserved decisions independently found one
   unsafe typed result and three materialization failures.

The replay is diagnostic evidence only. It made no provider calls and does
not replace or retry the terminal live attempt.

## Exact identity

- exact model: `gpt-5.4-nano-2026-03-17`;
- provider profile: `openai_gpt`;
- exact identity SHA-256:
  `aedaaab228200585b18a0649398dfc3a80fd2b369ff4efdabb983ded0be1c950`;
- model input:
  `broker_reports_gate2_financial_semantic_decision_packet_v5`;
- request profile: `financial_semantic_v5`;
- compact projection SHA-256:
  `6d17d46089b91cfb197dcad12f89635c5879173b6f2175d3810e6dd968361256`;
- Prompt SHA-256:
  `a9002b22a7f9b14122c7c2738307e39e425cc1356b7f38c9e48ff061aa23680c`;
- provider-schema set SHA-256:
  `39404e6324497bbb0700480f7361ecf0e007ffadc0f6fb96e2c6a797c9edfc54`;
- frozen benchmark SHA-256:
  `9e9c8006b71b7758981b46597d09c3e45ad60bdc80063263be0c3abecbd66fe7`;
- qualification authorization SHA-256:
  `74df5f51cfc6499ca3b0b2faebc0ff1dec12dc816bd67ff3717d8048937b7b67`.

The preflight for the merged revision passed with zero provider calls,
production admissions empty, and an estimated maximum cost of
USD `0.012993600`.

## Attempt accounting

- full-scope provider attempts: 1;
- semantic provider calls: 10;
- technical cases: 2;
- technical-case provider calls: 0;
- hidden retries: 0;
- fallback calls: 0;
- repair attempts: 0;
- customer calls: 0;
- input tokens: 20,599;
- output tokens: 1,824;
- actual cost: USD `0.006399800`;
- total provider latency: 29,853 ms;
- exact private checkpoints preserved outside Git: 10.

No second model attempt was made.

## Live terminal receipt

The live execution gate reported:

- semantic cases stopped by
  `financial_semantic_v5_provider_execution_identity_invalid`: 10;
- technical preclose cases passed: 2;
- exact returned decisions preserved: yes;
- official status: `MODEL_NOT_SAFE_FOR_SHADOW`.

This metadata failure is itself a qualification failure. The decisions were
then replayed offline to determine whether the model would have been safe if
that harness check had not stopped materialization.

## Offline exact-decision replay

The replay verified all ten canonical request hashes and all ten private
checkpoint hashes before reading the decisions.

Results:

- exact decisions replayed: 10;
- provider calls created by replay: 0;
- canonical decision validations passed: 10;
- all-case materializations passed: 9 of 12;
- unclassified value-loss failures: 2;
- date/period requirement failure: 1;
- unsafe typed: 1;
- typed precision: 80.00%;
- typed recall: 100.00%;
- safe under-typing: 0;
- unclassified semantic rate: 50.00%.

Replayed hard gates:

| Hard gate | Result |
|---|---:|
| Unsafe typed | 1 |
| Data loss | 2 |
| Inventions | 0 |
| Invalid refs | 0 |
| Wrong roles | 0 |
| Duplicate bindings | 0 |
| Cross-scope bindings | 0 |
| Ownership gaps | 3 |
| Canonical/materialization errors | 3 |

The replay therefore independently confirms
`MODEL_NOT_SAFE_FOR_SHADOW`.

## Stage rollback

After the terminal failure, the qualification-only Action was restored to
the exact pre-GOAL9A state to prevent another Nano V5 attempt:

- content SHA-256:
  `f178b142403e52897d2caf74ad75576162331efa85b0da85d472d8301ad24932`;
- metadata SHA-256:
  `6cf2907e2cff2e82a9dc212d27ead39e2bf0f2fe3dc035ba1d2c6e2ccf674bd7`;
- qualification policy SHA-256:
  `901c32f1afe865a835d849285862e8077bbe5f62b7690f63737accbe143a6ebe`;
- stage mutations in GOAL9B: 1;
- maintained functions unchanged: yes;
- published model inventory unchanged: yes;
- production admissions empty: yes;
- provider/customer calls during rollback: 0/0.

## Evidence and privacy

Repository-safe attempt receipt:

- internal integrity SHA-256:
  `5bed37eb950918530130e9eaca7ad5b315f13433092f5192636e2dd87440ed80`;
- copied file SHA-256:
  `aee92299066eba68fe76209945efcef12ec2e69a3f4994fc71ad9b8aae27171b`.

Repository-safe offline replay receipt:

- internal integrity SHA-256:
  `95b4dfcbd880c647c128b6603940d9947bfea19e54c400df1ef737097434c40e`;
- copied file SHA-256:
  `376fb6ed43e4fa7b7aec09c71c1c4ed25e9474957a0d432dc653f7fc49b976a2`.

The repository receipts contain hashes, counts, bounded classifications and
safe metrics only. Canonical requests, bindings, source refs, literals and
raw provider output remain outside Git.

## Acceptance and next boundary

- provider attempts: `EXACTLY_ONE`;
- hidden retry: `ZERO`;
- exact decisions preserved: `YES`;
- evidence PR: pending review and merge;
- product gate: `MODEL_NOT_SAFE_FOR_SHADOW`;
- runtime/product diff in this PR: `ZERO`.

GOAL 10 through GOAL 14 are stopped. Further provider work requires a
separate explicit model-or-policy decision program.
