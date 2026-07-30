# Broker Reports Gate 2 Type-First inactive implementation — GOAL 17

Status: **LOCAL IMPLEMENTATION PROOF PASSED; INACTIVE; NOT ADMITTED**.

This report proves the additive, fail-closed, zero-provider-call local implementation only. It does not qualify a provider model, activate runtime behavior, or create a production admission.

## Exact proof route

Packet candidate/private mapping → Choice response profile → Context Linter/sealed request → sealed-only Request Builder → generic OpenAI prepare/schema binding → one simulated terminal envelope → generic extraction → parser/Expansion → canonical validator/materializer → Financial Domain Catalog/Persistence → private Evidence → serialize/restore/exact replay.

No native transport, model-client execute method, provider call, retry, repair, fallback, runtime valve, product consumer or admission is present in that route.

## Result counts

| Measure | Total |
| --- | ---: |
| Successful full chains | 10 |
| Exact success replays | 10 |
| Adversarial cases | 21 |
| Exact technical-failure replays | 16 |
| Parser-invalid responses | 12 |
| Canonical decisions/materializations/snapshots | 10 / 10 / 10 |

Real compiler fixtures prove singleton-type cardinalities `0 / 1 / 2` as `0 / 1 / 2` complete validly prebound options.

Exact technical codes include `mapping_receipt_mismatch`, `pack_projection_drift` and `exact_code_owned_typed_option_mismatch`.

## Comparator diagnostics

| Counter | Total |
| --- | ---: |
| `plausible_type_set_exact_total` | 5 |
| `false_empty_total` | 1 |
| `false_singleton_total` | 2 |
| `false_superset_total` | 2 |
| `wrong_singleton_type_total` | 1 |
| `false_singleton_typed_total` | 2 |
| `unsafe_typed_total` | 3 |
| `safe_under_typing_total` | 2 |
| `invalid_response_total` | 12 |

The adversarial corpus intentionally demonstrates the unresolved false-singleton hazard: `false_singleton_typed_total = 2` and `unsafe_typed_total = 3`. The comparator records this after the product decision and performs no repair. Therefore these diagnostic hard-gate values are not an activation pass; production admission remains empty.

## Zero-call accounting

| Counter | Total |
| --- | ---: |
| Provider calls authorized | 0 |
| Provider submissions | 0 |
| Provider responses | 0 |
| Transport invocations | 0 |
| Retry / repair / semantic repair / fallback | 0 / 0 / 0 / 0 |
| Simulated terminal envelopes | 10 (1 per successful case) |

## Repository authority

- Contract integrity: `73f4ea51d8767b28fc8b3a9b1e12a6345f897ea8cbe8bde42decd0cb1ff70775`
- Safe receipt integrity: `572a68669e0bad43622242e44768cf9dc8cf73c57e61cfe8d18cfd35cab7ccf5`
- Gate 1 generated bundle: `6101dd72c74ea8e968d47b4158a2b433f271fb377047ff8772fbad0c2bac406b`
- Gate 2 source generated bundle: `61b692821de093423e594fc0339762136f58a11c3b9a41f3e5af32f45b36fef7`
- Gate 2 domain generated bundle: `a4f4042f39b2a4bac225aecf58cad047f0d74f35b0a1b6cb9e68740e87a657e6`

The three bundle changes are deterministic closed-world copies of the maintained Broker Reports owner/support modules. Bundle topology and product consumer count remain unchanged.

## Reproduction

From `services/broker-reports-gate1-proof`:

```text
python scripts/build_type_first_zero_call_e2e_evidence.py --check
python -m pytest -q tests/test_broker_reports_gate2_type_first_e2e.py
```

The safe receipt contains only allowlisted identities, hashes, counts, outcome/error classes and zero-call accounting. Private requests, simulated envelopes, source refs, literals, snapshots and authority keys are not written to Git.
