# Broker Reports — Answer Context Stitch Atomic Release

Date: 2026-07-23

Branch: `codex/broker-reports-answer-context-stitch-release-v1`

Status: `PASSED`

## Release

- exact source revision:
  `287d2bd255a8023b076a3fa0e688f18e3f509a04`;
- release ID: `broker-reports-287d2bd255a8`;
- manifest SHA-256:
  `ca8be13b724eceff7a5735568cf6a18ea7928d5419ebbe683804d634d6b462c8`;
- rollback identity SHA-256:
  `ce4c179a95cca4ae40fb61545e1219c4ffc517968130b7a3a529a69534808eca`.

The first command attempt combined rollback proof with a dry run and was
rejected before mutation with
`stage_release_rollback_proof_requires_apply`. The corrected dry validation
then passed. This command error caused no stage change and is not hidden from
the evidence.

The maintained atomic apply completed with:

- three Function health checks passed;
- rollback artifact created;
- previous state restoration proved;
- candidate state restoration proved;
- release staging removed;
- nonterminal workload jobs: 0;
- owned temporary entries: 0.

## Exact live identities

| Runtime object | SHA-256 |
|---|---|
| `broker_reports_gate1_pipe` | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` |
| `broker_reports_gate2_source_fact_pipe` | `a6df7853e7cf40676fd4483feeac0d8d136b2121967e6f0df39f8d85324df32a` |
| `broker_reports_gate2_domain_source_fact_pipe` | `1bb11d428cb9082edec388109839e7f2f3117447daefe9470129bc2413ed1499` |
| `broker_reports_private_intake_action` | `874a07129aa626e61807095b19e531972395934ce1a9aad72d378a3104530ae4` |
| loader | `28c5eadf6839d9aac5db4f125c31bda5ca6f08d9ce82723c832dd319126703b2` |

Image identity remained exact and unchanged. All 12 managed prompts remained
exact and required no update.

## Counter invariants

Before and after values were identical:

| Counter | Before | After |
|---|---:|---:|
| Knowledge rows | 0 | 0 |
| Document rows | 0 | 0 |
| File rows | 272 | 272 |
| Vector files | 595 | 595 |
| Vector bytes | 309,808,908 | 309,808,908 |

No Knowledge/RAG/vector mutation occurred.

## Independent verification

Atomic-release verifier:

- status: passed;
- Functions: 3/3;
- prompts: 12/12;
- Action, loader, image and rollback identity: exact;
- workload quiescent: yes.

Repository/live delivery verifier:

- status: passed;
- Function bundles: 3/3 exact;
- prompts: 12/12 exact;
- factory boundary: passed;
- provider profiles: complete;
- PyMuPDF identity: exact.

The next mandatory step is the fresh browser click-through on this release.
