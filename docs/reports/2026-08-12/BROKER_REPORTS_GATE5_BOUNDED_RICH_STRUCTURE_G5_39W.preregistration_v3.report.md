# G5.39W Phase A preregistration v3

Status: **FINAL V2 TRANSPORT FREEZE BEFORE PROVIDER SUBMISSION**
Date: 2026-08-12

This document retires the original 16 implicit-v1 slot IDs and freezes 16 new
v2-suffixed slot IDs. It changes transport integration only. Corpus,
representations, model-visible bytes, prompts, response schema, repetitions,
budgets, metrics, oracle, hard failures, and Phase A threshold remain
byte-identical to the prior plan.

## Retired v1 attribution

The first execution attempt claimed 16 slots but produced no inference:

- 15 slots reached the factory and failed before submission with
  ModuleNotFoundError because the local process did not contain the in-process
  OpenWebUI completion module;
- the final claimed slot stopped at OpenWebUI sign-in rate limiting before a
  factory client was created;
- provider submissions across all retired slots: 0;
- provider responses across all retired slots: 0;
- model outputs: 0;
- retired-result aggregate SHA-256:
  fe96383e414ca3d1f77b69de464bf6ae1e82f287df18e08c76c031c7a729f350.

The implicit-v1 slot IDs will never be reused. These were pre-inference
transport/setup failures, so a new frozen experiment version is permitted by
the original retry policy.

## Canonical completion boundary

The repository already owns a live research completion boundary:

    Gate2StructuredModelClientFactory.create
    → label_gate3_once
    → sealed final form_data
    → injected completion_resolver
    → authenticated OpenWebUI /api/chat/completions
    → configured provider/model

The v2 adapter reuses that exact boundary. It does not call a provider API or
SDK directly. One authenticated OpenWebUI session is reused only as transport;
each of the 16 slots creates a new factory client and executes one independent
model call.

## Frozen v2 experiment identity

- Isolated research commit:
  e77621008af6c573e3161cc353b3186998912fc0.
- Isolated research tree:
  2c5465d233a594486383b07aebe4e82b5a2a139b.
- Phase A code SHA-256:
  c3b42db545ad79a2bbad2e62310c29b52eb6d5800b33fe4a0626d65040128da8.
- Phase A v2 plan SHA-256:
  5caf9d2029702f1424f9e349c3d6319521e6ee3ecaa6a36d953ff5ca18d70850.
- Phase A tests SHA-256:
  024369deb74c358ec29782d7ccde1aaef82b2786c81bd30c4ac9d1ff5ec1a65e.
- Phase A prepared private input SHA-256:
  8c2cc837a89af0de91a6755d877c91ea403a49ca4d591e90a00a11e68aeb1aa3.
- Phase A v2 safe preflight SHA-256:
  a5d92799a48b12a484b7d37f7dfc375e0da83e5a111018706286f612d88e7be3.

## V2 preflight

- Frozen published model present: yes.
- Factory request/profile exact: 16/16.
- Final provider context exact: 16/16.
- Canonical schema hash exact: 16/16.
- Gemini schema transformations: 10 for every slot.
- Completion boundary:
  authenticated OpenWebUI /api/chat/completions.
- V2 claimed slots before this freeze: 0.
- V2 provider submissions before this freeze: 0.

## Deterministic contract verification

Six tests passed in 0.204 seconds:

1. IA is exact Stage C canonical serialization.
2. IB preserves every structure item exactly once and in source order.
3. Response schema is closed and terminal.
4. The two NEGATIVE_AB events expand to disjoint ref components.
5. Exactly 16 unique v2 slots exist, two per hypothesis/case.
6. The completion boundary submits the exact sealed form once and returns its
   terminal response without mutation.

The HTTP session is the only mocked external boundary in test 6. The factory,
representation, schema, plan, and adjudicator under test are not mocked.

All v2 outputs count. Semantic retry, repair, answer merge, follow-up
correction, and best-of-N remain zero/false.
