# Broker Reports Gate 1 Visual Neutral Table Closure Report

Date: 2026-07-20
Program status: **NOT_CLOSED**

## Outcome

The bounded visual-neutral-table contour is implemented and proven against the
actual approved corpus without provider calls or mutation of the golden
ArtifactStore. It does not close Goal 3: ten of eleven claimed material visual
scopes are accepted; one source scope is physically byte-uniform and remains
unresolved.

No material scope was reclassified to make the count pass. No OCR or table model
was granted canonical authority.

## Actual-corpus accounting

| Invariant | Result |
| --- | ---: |
| Material source identities | 12 |
| Exact duplicate identities | 1 |
| Unique material image scopes | 11 |
| Accepted unique scopes | 10 |
| Deterministic accepted scopes | 1 |
| Operator-reviewed accepted scopes | 9 |
| Unresolved byte-uniform scopes | 1 |
| Unsupported complex-layout scopes | 0 |
| Accepted regions / neutral tables | 17 / 17 |
| Accepted neutral cells | 623 |
| Promotion replays | 17 |
| Continuation pages validated | 6 |

Terminal-state accounting passed, but the required 11/11 acceptance invariant
did not. The committed aggregate evidence is
`BROKER_REPORTS_GATE1_VISUAL_NEUTRAL_TABLE_ACTUAL_CORPUS.v2.safe.json`; all
customer-bearing observations and canonical cells remain in ignored private
proof storage.

## Holdout and negative evidence

The frozen detector selected the first audit-order simple grid with a text/layout
sibling; the job manifest had not supplied its geometry. The holdout was accepted
and its OCR tokens had 1.0 set overlap with the independent layout sibling.

An actual non-table visual scope was evaluated across the frozen orientation and
grid detector. It produced zero grid regions and zero promotions. The materially
different complex scan was reconstructed as five bounded physical regions,
passed deterministic validation, and was accepted only after technical review.
Model topology was not used as authority.

These checks are evidence for this bounded profile. One holdout does not prove
generalization to arbitrary broker-report layouts.

## Safety and runtime evidence

- Provider calls, retries, tokens, cost, and whole-document uploads: zero.
- `model_canonical_authority`: false.
- Golden ArtifactStore before/after snapshot: unchanged.
- An isolated disposable clone persisted 18 immutable visual results: 17
  accepted and one blocked terminal result.
- Gate 2 consumed the 17 accepted artifacts as 17 validated canonical packages
  for five documents with zero validation errors; the clone remained unchanged
  during read-only package preparation.
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

- Actual-corpus readiness: **partial, 10/11 claimed material scopes accepted**.
- Accepted-scope Gate 2 readiness: **17/17 canonical packages validated**.
- Bounded physical-grid profile: **proven on the accepted scopes plus one actual
  holdout and one actual negative**.
- Generalization readiness: **not proven**.
- Release readiness: **not claimed**.
- Customer acceptance: **not claimed**.

Goal 3 can close only when the remaining claimed material scope has honest
terminal evidence satisfying the required canonical acceptance invariant, or
when the authorized source owner corrects the underlying evidence. The current
byte-uniform source cannot be repaired by OCR and was not reclassified merely to
make the denominator pass.

The separate maintained source-binary proof confirms that this is the only blank
page in its 19-page PDF: page 8 has zero content streams, bytes, text, images,
XObjects, drawings, links, and annotations, while all other 18 pages are
contentful. Two exact source copies and both normalized renders agree. See
`BROKER_REPORTS_GATE1_VISUAL_SOURCE_CORRECTION_REQUIRED.v1.safe.json`.
