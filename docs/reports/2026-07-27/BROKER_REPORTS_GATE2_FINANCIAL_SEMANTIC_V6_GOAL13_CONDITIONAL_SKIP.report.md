# Broker Reports Gate 2 Financial Semantic V6 Goal 13 Conditional Skip

Date: 2026-07-27  
Goal: 13  
Repository base: `9a004cd5a607c0b974ca912144e0ed9e571c013f`  
Goal status: `SKIPPED_PREREQUISITE_NOT_MET`

## Required prerequisite

Goal 13 permits a bounded authorized actual-corpus shadow only when one exact
V6 model has terminal product status `MODEL_SAFE_FOR_SHADOW`.

No model meets that prerequisite:

| Exact model | Terminal status | Receipt integrity |
| --- | --- | --- |
| `gpt-5.4-nano-2026-03-17` | `MODEL_NOT_SAFE_FOR_SHADOW` | `c263b2dca517a7b9fbcab100bcadf7331739d7f349bc009601a625a1e651a640` |
| `claude-haiku-4-5-20251001` | `MODEL_NOT_SAFE_FOR_SHADOW` | `774b58a9c23cdcd943154cd448b44458a769dbb255d8ff05aba4738fe8a508dd` |

The terminal receipts are already preserved in `main`. Neither candidate may
be rerun under its consumed identity.

## Enforced stop

The bounded actual-corpus shadow was not started.

| Measure | Result |
| --- | ---: |
| Actual-corpus provider calls | 0 |
| Customer/private records read | 0 |
| Shadow artifacts written | 0 |
| Stage mutations | 0 |
| Production admissions | 0 |
| Fallbacks | 0 |
| Repairs | 0 |
| Hidden retries | 0 |

Goal 13 acceptance items are not evaluated because executing them without a
safe exact model would violate the prerequisite:

- `ACTUAL_CORPUS_COVERAGE`: `NOT_RUN`;
- `UNSAFE_TYPED`: `NOT_RUN`;
- `UNCLASSIFIED_VALUE_LOSS`: `NOT_RUN`;
- `MATERIALIZATION_FAILURES`: `NOT_RUN`;
- `DOMAIN_QUERIES`: `NOT_RUN`.

This is a prerequisite stop, not an actual-corpus failure and not a claim of
shadow readiness.

## Next permitted goal

Goal 14 has no model-safety prerequisite. It may prove the existing Gate 3
domain-only boundary and frozen full-scope baseline without invoking a model,
activating V6, or changing production admissions.
