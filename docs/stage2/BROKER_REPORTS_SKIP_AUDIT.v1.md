# Broker Reports Skip Audit v1

Status: complete

Effective date: 2026-07-31

Per-test machine authority: `BROKER_REPORTS_SKIP_AUDIT.v1.json`

## Result

```text
original_skips = 3
REMOVE_NOW = 0
REMOVE_NOW_FIXED = 0
JUSTIFIED_CONDITIONAL_SKIP = 0
HISTORICAL_GUARD = 3
PLATFORM_UNAVAILABLE = 0
TEST_DEBT = 0
final_skips = 3
new_skips = 0
unclassified_skips = 0
unjustified_kt2_blocking_skips = 0
```

The retired PDF strategy benchmark and its conditional skips were removed with
the rejected local PDF engine. Only the three historical exact-diff guards
remain current.

## Historical guards

| Test | Condition | Owner | Classification | Removable |
| --- | --- | --- | --- | ---: |
| GOAL 14 exact-diff guard | report absent from active change-set | Evidence Builder Maintainers | `HISTORICAL_GUARD` | no, unless the historical builder contract is retired |
| GOAL 15 exact-diff guard | report absent from active change-set | Evidence Builder Maintainers | `HISTORICAL_GUARD` | no, unless the historical builder contract is retired |
| GOAL 16 exact-diff guard | report absent from active change-set | Evidence Builder Maintainers | `HISTORICAL_GUARD` | no, unless the historical builder contract is retired |

These guards do not skip the underlying builders, integrity checks, or current
architecture tests. They only avoid applying an old branch-diff assertion to a
different change-set.
