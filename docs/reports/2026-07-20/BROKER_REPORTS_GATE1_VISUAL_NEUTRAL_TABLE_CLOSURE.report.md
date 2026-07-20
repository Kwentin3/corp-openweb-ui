# Broker Reports Gate 1 Visual Neutral Table Closure Report

Date: 2026-07-20  
Program status: **NOT_CLOSED**

## Outcome

The bounded visual-neutral-table contour is implemented and proven against the
actual approved corpus without provider calls or ArtifactStore mutation. It does
not close Goal 3: nine of eleven unique material visual scopes are accepted; one
byte-uniform source scope remains unresolved and one materially different scan
fails closed outside the frozen physical-grid profile.

No material scope was reclassified to make the count pass. No OCR or table model
was granted canonical authority.

## Actual-corpus accounting

| Invariant | Result |
| --- | ---: |
| Material source identities | 12 |
| Exact duplicate identities | 1 |
| Unique material image scopes | 11 |
| Accepted unique scopes | 9 |
| Deterministic accepted scopes | 1 |
| Operator-reviewed accepted scopes | 8 |
| Unresolved byte-uniform scopes | 1 |
| Unsupported complex-layout scopes | 1 |
| Accepted regions / neutral tables | 12 / 12 |
| Accepted neutral cells | 410 |
| Promotion replays | 12 |
| Continuation pages validated | 6 |

The exact terminal-state invariant passed. The committed aggregate evidence is
`BROKER_REPORTS_GATE1_VISUAL_NEUTRAL_TABLE_ACTUAL_CORPUS.v1.safe.json`; all
customer-bearing observations and canonical cells remain in ignored private
proof storage.

## Holdout and negative evidence

The frozen detector selected the first audit-order simple grid with a text/layout
sibling; the job manifest had not supplied its geometry. The holdout was accepted
and its OCR tokens had 1.0 set overlap with the independent layout sibling.

An actual non-table visual scope was evaluated across the frozen orientation and
grid detector. It produced zero grid regions and zero promotions. The materially
different complex scan was retained as `unsupported_visual_layout`; crop/scale
changes had produced unstable model topology, so model output was not promoted.

These checks are evidence for this bounded profile. One holdout does not prove
generalization to arbitrary broker-report layouts.

## Safety and runtime evidence

- Provider calls, retries, tokens, cost, and whole-document uploads: zero.
- `model_canonical_authority`: false.
- ArtifactStore before/after snapshot: unchanged.
- Customer values and source identities in committed proof: false.
- Private payloads were resolved through `ArtifactResolver`; original files were
  not read directly.
- OCR observations were repeated; low-confidence or repeat uncertainty required
  a sealed technical-operator review.
- The PaddleOCR native repeated-call memory failure was contained by one isolated
  process per double-OCR region. This changes adapter lifecycle only, not the
  promotion contract.

## Contract and verification

The production contract is
`docs/stage2/contracts/BROKER_REPORTS_GATE1_VISUAL_NEUTRAL_TABLE.v1.md`. The
implementation is factory-routed, bundle-compatible, and free of PaddleOCR,
OpenCV, provider SDK, and filesystem dependencies. The local proof adapter owns
those optional dependencies and cannot promote around the factory.

Focused verification covers deterministic and reviewed promotion, blank and
provider-disabled terminal states, grid omission/duplication, OCR substitution,
decimal drift, column reorder, header hierarchy, totals, false merge/boundary,
continuation, access/source-image drift, malformed input, and result tampering.

## Readiness statement

- Actual-corpus readiness: **partial, 9/11 unique material scopes accepted**.
- Bounded physical-grid profile: **proven on the accepted scopes plus one actual
  holdout and one actual negative**.
- Generalization readiness: **not proven**.
- Release readiness: **not claimed**.
- Customer acceptance: **not claimed**.

Goal 3 can close only when both remaining material scopes have honest terminal
evidence satisfying the required canonical acceptance invariant, or when an
authorized source correction changes the underlying evidence. The current blank
source cannot be repaired by OCR, and the unstable complex scan needs a separate
topology profile or an explicit reviewed reconstruction contract.
