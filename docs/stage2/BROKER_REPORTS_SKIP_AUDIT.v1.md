# Broker Reports Skip Audit v1

Status: complete

Effective date: 2026-07-31

Per-test machine authority: `BROKER_REPORTS_SKIP_AUDIT.v1.json`

## Result

```text
original_skips = 23
REMOVE_NOW = 18
REMOVE_NOW_FIXED = 18
JUSTIFIED_CONDITIONAL_SKIP = 2
HISTORICAL_GUARD = 3
PLATFORM_UNAVAILABLE = 0
TEST_DEBT = 0
final_skips = 5
new_skips = 0
unclassified_skips = 0
unjustified_kt2_blocking_skips = 0
```

The original class-wide `REFERENCE_PATH.exists()` decorator disabled 20 PDF
benchmark tests. Source inspection proved that only two tests read the private
reference. The condition now applies to those two methods only; the other 18
execute unconditionally. This is a test-integrity repair, not a product change.

## Original PDF benchmark skips

All rows are owned by the PDF Benchmark Maintainers unless the Evidence
Custodian is named. All are reproducible and non-blocking for KT2.

| Test method | Needs private reference | Classification | Final state |
| --- | ---: | --- | --- |
| `test_bbox_order_is_explicit_in_every_v2_prompt_and_schema` | no | `REMOVE_NOW` | runs |
| `test_crop_bbox_projection_is_exact_and_does_not_mutate_input` | no | `REMOVE_NOW` | runs |
| `test_currency_column_split_is_structure_error_not_value_invention` | no | `REMOVE_NOW` | runs |
| `test_currency_symbol_remains_unknown_and_usd_inference_is_detected` | no | `REMOVE_NOW` | runs |
| `test_detection_validator_is_closed_and_requires_explicit_uncertainty` | no | `REMOVE_NOW` | runs |
| `test_evidence_overlay_is_non_mutating_and_has_all_terminal_statuses` | no | `REMOVE_NOW` | runs |
| `test_frozen_manifest_and_reference_have_exact_scope_and_hash_binding` | yes | `JUSTIFIED_CONDITIONAL_SKIP` | conditional; Evidence Custodian |
| `test_manifest_validator_rejects_reference_leakage` | no | `REMOVE_NOW` | runs |
| `test_manifest_validator_rejects_retry_and_failover` | no | `REMOVE_NOW` | runs |
| `test_operation_cost_prices_inferred_thinking_at_output_rate` | no | `REMOVE_NOW` | runs |
| `test_provider_operation_calls_adapter_once_with_single_attempt_lineage` | no | `REMOVE_NOW` | runs |
| `test_run_help_exposes_no_reference_argument` | no | `REMOVE_NOW` | runs |
| `test_runner_source_enforces_factory_route_and_has_no_retry_transport` | no | `REMOVE_NOW` | runs |
| `test_scorer_attempts_missing_reference_only_after_terminal_verification` | no | `REMOVE_NOW` | runs |
| `test_scorer_minimal_smoke_uses_tracked_reference_after_seal` | yes | `JUSTIFIED_CONDITIONAL_SKIP` | conditional; Evidence Custodian |
| `test_scorer_rejects_terminal_tamper_before_reference_access` | no | `REMOVE_NOW` | runs |
| `test_strategy_c_replays_b_extraction_without_provider_operation` | no | `REMOVE_NOW` | runs |
| `test_two_step_detection_is_scored_when_crop_extraction_is_invalid` | no | `REMOVE_NOW` | runs |
| `test_unified_validator_enforces_closed_rectangular_and_explicit_empty` | no | `REMOVE_NOW` | runs |
| `test_unified_validator_preserves_explicit_ambiguity` | no | `REMOVE_NOW` | runs |

## Historical guards

| Test | Condition | Owner | Classification | Removable |
| --- | --- | --- | --- | ---: |
| GOAL 14 exact-diff guard | report absent from active change-set | Evidence Builder Maintainers | `HISTORICAL_GUARD` | no, unless the historical builder contract is retired |
| GOAL 15 exact-diff guard | report absent from active change-set | Evidence Builder Maintainers | `HISTORICAL_GUARD` | no, unless the historical builder contract is retired |
| GOAL 16 exact-diff guard | report absent from active change-set | Evidence Builder Maintainers | `HISTORICAL_GUARD` | no, unless the historical builder contract is retired |

These guards do not skip the underlying builders, integrity checks, or current
architecture tests. They only avoid applying an old branch-diff assertion to a
different change-set.
