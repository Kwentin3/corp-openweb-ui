# Broker Reports DOC25 Shadow Run Plan v1

Status: `READY_FOR_CONTROLLED_SYNTHETIC_SHADOW_ACTUAL_CORPUS_NOT_RUN`

Date: 2026-08-05

## Configuration

| Valve | Controlled shadow | Product default |
| --- | --- | --- |
| `CANONICAL_GATE2_WRITE_ENABLED` / `canonical_gate2_write_enabled` | `true` | `false` |
| `CANONICAL_GATE2_READ_ENABLED` / `canonical_gate2_read_enabled` | `false` | `false` |
| `CANONICAL_GATE2_COMPARE_ENABLED` / `canonical_gate2_compare_enabled` | `true` | `true`, inert while write is false |

Legacy `gate2_handoff_v0` remains authoritative in all shadow runs.

## Execution protocol

1. Use a dedicated test tenant/case/chat/workspace and the existing explicit
   retention policy.
2. Enable write and compare only for the bounded run.
3. Keep canonical reads disabled for product consumers.
4. Normalize through the normal Gate1 pipe; do not call adapters directly.
5. Resolve original source, canonical candidate and compare receipt under the
   same authenticated context.
6. Record only aggregate counts, hashes, status codes and timing in Git.
7. Keep source bytes, canonical private payloads and paths outside Git.
8. Disable write after the run; no retry, provider call, parser fallback or
   consumer cutover is permitted by this plan.

## Required metrics

- input/source/canonical/compare/failure terminal counts;
- schema and canonical-root-hash validation;
- container/node/table counts by format;
- legacy scalar/text accounting versus canonical accounting;
- order/provenance status;
- critical-loss status;
- write latency and payload bytes;
- scope-denial and lifecycle checks;
- legacy handoff success and authority status.

`inconclusive` is terminal and cannot be reported as parity.

## Stop and rollback

Stop on the first schema, ref, scope, order, lifecycle or critical-loss failure.
Rollback is immediate valve disablement because no consumer reads canonical
data. Candidate records then expire/purge under their existing retention
policy. There is no active pointer to roll back in the current slice.

## Current execution record

Synthetic focused execution passed. DOC23/DOC24 safe receipts validate, but no
current private actual-corpus shadow run was executed. This plan does not
authorize product cutover.

