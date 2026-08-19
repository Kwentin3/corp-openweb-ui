# G5.39W Phase A preregistration v2

Status: **FINAL FREEZE BEFORE PROVIDER SUBMISSION**
Date: 2026-08-12

This document supersedes the initial G5.39W preregistration only by sealing the
now-complete experimental code, plan, tests, and provider preflight. Corpus,
representations, prompts, response contract, repetitions, budgets, metrics,
hard failures, and Phase A threshold are unchanged.

## Zero-call setup attribution

Two setup defects were found before any slot claim or provider submission:

1. the SSH command that read current OpenWebUI provider configuration did not
   preserve the remote Python command quoting;
2. the first reader looked for persistent fields in the database document
   rather than the live OpenWebUI configuration owner consumed by the
   production factory.

Both failures occurred during read-only preflight. Provider submissions: 0.
Claimed slots: 0. No model output existed. The corrected preflight now reads
the live OpenWebUI configuration owner without publishing credentials and
does not alter any experiment input or evaluator rule.

## Frozen experiment identity

- Isolated research commit:
  e4e5e2e1e672e4254818d70f23c3da461cd13ef7.
- Isolated research tree:
  45734534a194df5546c2e1429b97eaf3d62b3b42.
- Phase A code SHA-256:
  0358138d5566f03be2c82912202f9400eaf094fe19796eb3bb6a5e9bffbe3568.
- Phase A plan SHA-256:
  edc7fefb6b60111a6dae9ba7266f4a9f70d2baba6e681c27f155543b023345fe.
- Phase A tests SHA-256:
  ba332985467c7912a980f3f1bcad6ad08e840d06e5f4a3619fde6f204edd121d.
- Response schema SHA-256:
  1b93d6f377f0a67ff7109d78e29f953fbbdc399f4924a8de7bc4e942b971efcf.
- Neutral system prompt SHA-256:
  efb620c18aa5d06a2a1dcac919f6bfa864a99a9683b9dcd13d8d0547209eeaf4.
- Neutral task SHA-256:
  5f2453f9a1e29f5bae32714119d6880a174800e7138c13a82dc7538f7e7f3854.
- Safe preflight SHA-256:
  cd5a2b06524ae69aecea556b74a4258ec163343b3ae8d24eff91aba6fd90a984.

## Preflight result

- Exact provider/model:
  google_gemini / models/gemini-3.5-flash.
- Factory route:
  Gate2StructuredModelClientFactory.create.label_gate3_once.
- Slots checked: 16/16.
- Final provider context exact: 16/16.
- Canonical schema hash exact: 16/16.
- Gemini schema transformations: 10 for every slot.
- Provider connection matches: exactly 1.
- API credential present: yes, value not retained in safe evidence.
- Provider submissions: 0.

The production factory route was used for request sealing. No direct provider
request is permitted in the experimental code.

## Deterministic contract tests

Five tests passed:

1. IA is the exact existing Stage C canonical serialization.
2. IB preserves each table, row, cell, ref, literal, relation, and source order
   exactly once.
3. The response schema is closed and rejects non-terminal statuses/extras.
4. NEGATIVE_AB expands its two explicit relations into two disjoint complete
   event components for adjudication.
5. The plan contains exactly 16 unique slots, two per
   hypothesis/case pair.

The unit under test was not mocked. No provider call occurs in these tests.
Observable terminal output is the exact representation/schema/plan invariant.

All 16 slots are now immutable. Each may be claimed once and may submit at
most once. Every result counts.
