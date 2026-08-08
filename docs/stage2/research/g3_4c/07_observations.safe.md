# G3.4C observations

Status: `REVIEW_REQUIRED`

Date: 2026-08-07

## Compact alias-format rejection

The compact response had the expected closed top-level shape, exact schema
version and four known financial labels, but each target alias included
display brackets. Bare aliases are required. The full response was therefore
rejected with `gate3_labeling_response_contract_invalid`; retry and repair were
not attempted.

This is blocking for G3.5 readiness because the batch is explicitly
incomplete. It does not invalidate the G3.4C route proof: rejection was
terminal, fail-closed and correctly accounted.

## REPO claim boundary

Five of 76 chunks were selected structurally: one whole table and four chunks
covering the first, middle, adjacent and final boundaries of the largest
oversized table. All five validated with empty sparse annotations. This proves
the bounded route on the predeclared shape; it does not establish whole-REPO
semantic completeness.

## Semantic coverage

Ten specimens were manually reviewed. Nine were correct labels or correct
omissions, with no observed false positive, wrong label, obvious missed fact
or adjudicated boundary failure. The tenth belonged to the rejected compact
response. Positive accrued-coupon-component and securities-lending specimens
were not observed, and the positive compact coupon did not produce a validated
sidecar.

Consequently semantic quality is `PARTIAL`, and G3.5 is not recommended until
the human review resolves the alias-format failure and the positive coverage
gaps.

## Character bound

The 60,000-character bound is `ADEQUATE_FOR_MVP` for the measured corpus. It
should remain unchanged: the live data shows a large peak reduction, and the
one rejection is independent of request size.
